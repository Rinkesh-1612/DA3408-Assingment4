"""Streamlit app that captions images on the CPU. It sends metrics to Prometheus."""
import io
import os
import time
import zipfile

import streamlit as st
import torch
from PIL import Image, UnidentifiedImageError
from streamlit.runtime.scriptrunner import get_script_run_ctx
from transformers import BlipForConditionalGeneration, BlipProcessor

import metrics as m

MODEL_NAME = "Salesforce/blip-image-captioning-base"
METRICS_PORT = int(os.getenv("METRICS_PORT", "28000"))
MAX_ZIP_IMAGES = int(os.getenv("MAX_ZIP_IMAGES", "50"))
MAX_ZIP_MB = int(os.getenv("MAX_ZIP_MB", "100"))
MAX_SIDE = 512  # Make large images smaller. This limits CPU and memory use.
IMG_EXT = (".jpg", ".jpeg", ".png", ".bmp", ".webp")

torch.set_num_threads(max(1, (os.cpu_count() or 2) - 1))
st.set_page_config(page_title="Image Captioning", page_icon="🖼️", layout="wide", initial_sidebar_state="expanded")


@st.cache_resource
def boot():
    m.start(METRICS_PORT, MODEL_NAME)
    t0 = time.perf_counter()
    proc = BlipProcessor.from_pretrained(MODEL_NAME)
    model = BlipForConditionalGeneration.from_pretrained(MODEL_NAME).eval()
    m.MODEL_LOAD_S.set(time.perf_counter() - t0)
    m.MODEL_LOADED.set(1)
    return proc, model


def client_labels():
    """Return the session ID and source IP. The app uses them as metric labels. The session ID is short, to limit label values."""
    ctx = get_script_run_ctx()
    sid = (ctx.session_id[:8] if ctx else "unknown")
    ip = "unknown"
    try:
        h = st.context.headers
        ip = (h.get("X-Forwarded-For") or getattr(st.context, "ip_address", None) or "unknown")
        ip = str(ip).split(",")[0].strip() or "unknown"
    except Exception:
        pass
    return sid, ip


def caption_image(img: Image.Image, mode: str) -> str:
    proc, model = boot()
    t0 = time.perf_counter()
    img = img.convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    inputs = proc(images=img, return_tensors="pt")
    m.PREPROCESS.labels(mode).observe(time.perf_counter() - t0)
    t1 = time.perf_counter()
    with torch.inference_mode():
        out = model.generate(**inputs, max_new_tokens=30, num_beams=3)
    m.INFERENCE.labels(mode).observe(time.perf_counter() - t1)
    text = proc.decode(out[0], skip_special_tokens=True)
    m.CAPTION_WORDS.labels(mode).observe(len(text.split()))
    return text


def process_one(data: bytes, mode: str, sid: str, ip: str):
    m.IMAGE_BYTES.labels(mode).observe(len(data))
    m.BYTES_IN.labels(mode).inc(len(data))
    try:
        cap = caption_image(Image.open(io.BytesIO(data)), mode)
        m.IMAGES.labels(mode, "success", sid, ip).inc()
        return cap
    except (UnidentifiedImageError, OSError):
        m.ERRORS.labels(mode, "bad_image").inc()
    except Exception:
        m.ERRORS.labels(mode, "inference").inc()
    m.IMAGES.labels(mode, "error", sid, ip).inc()
    return None


def run_single(file, sid, ip):
    mode = "single"
    m.REQUESTS.labels(mode, sid).inc()
    m.LAST_REQ_TS.set_to_current_time()
    m.ACTIVE.labels(mode).inc()
    t0 = time.perf_counter()
    try:
        data = file.getvalue()
        st.image(data, width=400)
        with st.spinner("Generating caption…"):
            cap = process_one(data, mode, sid, ip)
        if cap:
            st.success(cap)
        else:
            st.error("Could not caption this file.")
    finally:
        m.ACTIVE.labels(mode).dec()
        m.REQUEST_LAT.labels(mode).observe(time.perf_counter() - t0)


def run_bulk(file, sid, ip):
    mode = "bulk"
    m.REQUESTS.labels(mode, sid).inc()
    m.LAST_REQ_TS.set_to_current_time()
    m.ACTIVE.labels(mode).inc()
    t0 = time.perf_counter()
    zb = file.getvalue()
    m.ZIP_BYTES.observe(len(zb))
    m.BYTES_IN.labels(mode).inc(len(zb))
    try:
        if len(zb) > MAX_ZIP_MB * 1024 * 1024:
            m.ERRORS.labels(mode, "zip_too_large").inc()
            st.error(f"ZIP larger than {MAX_ZIP_MB} MB.")
            return
        try:
            zf = zipfile.ZipFile(io.BytesIO(zb))
        except zipfile.BadZipFile:
            m.ERRORS.labels(mode, "bad_zip").inc()
            st.error("Not a valid ZIP file.")
            return
        names = []
        for n in zf.namelist():
            base = os.path.basename(n)
            if n.endswith("/") or base.startswith(".") or "__MACOSX" in n:
                m.SKIPPED.labels("hidden_or_dir").inc()
            elif not base.lower().endswith(IMG_EXT):
                m.SKIPPED.labels("not_image").inc()
            else:
                names.append(n)
        if len(names) > MAX_ZIP_IMAGES:
            m.SKIPPED.labels("over_limit").inc(len(names) - MAX_ZIP_IMAGES)
            st.warning(f"Only the first {MAX_ZIP_IMAGES} images are processed.")
            names = names[:MAX_ZIP_IMAGES]
        m.BATCH_SIZE.observe(len(names))
        m.BULK_REMAINING.set(len(names))
        bar, rows = st.progress(0.0), []
        for i, n in enumerate(names, 1):
            cap = process_one(zf.read(n), mode, sid, ip)
            rows.append({"file": n, "caption": cap or "⚠ failed"})
            m.BULK_REMAINING.set(len(names) - i)
            bar.progress(i / len(names), text=f"{i}/{len(names)}")
        st.dataframe(rows, use_container_width=True)
    finally:
        m.BULK_REMAINING.set(0)
        m.ACTIVE.labels(mode).dec()
        m.REQUEST_LAT.labels(mode).observe(time.perf_counter() - t0)


st.title("🖼️ Image Captioning — in plain English")
st.markdown(
    "Upload a picture and this app **describes it in one sentence**, for example "
    "*“a dog running on a beach”*. It uses a small AI model (BLIP) that runs on an ordinary CPU, "
    "so no graphics card is needed."
)
boot()
sid, ip = client_labels()

c1, c2, c3 = st.columns(3)
c1.markdown("**1 · Choose**  \nPick one image, or a ZIP file that holds many images.")
c2.markdown("**2 · Caption**  \nPress the button. A caption takes a few seconds per image on a CPU.")
c3.markdown("**3 · Watch**  \nEvery request is measured and shown live on the Grafana dashboard.")

with st.sidebar:
    st.header("About")
    st.markdown(
        "This app is a **monitoring demo**. While you use it, it records numbers such as "
        "how many images were captioned, how long each took, and how busy the CPU is."
    )
    st.subheader("Limits")
    st.markdown(
        f"- ZIP: up to **{MAX_ZIP_IMAGES} images** and **{MAX_ZIP_MB} MB**\n"
        f"- Images are shrunk to **{MAX_SIDE}px** before captioning\n"
        "- Other files in a ZIP (folders, text, hidden files) are skipped"
    )
    st.subheader("Your session")
    st.markdown(f"Session ID: `{sid}`  \nSource IP: `{ip}`")
    st.caption("These two values label your requests in the metrics (client tracking).")
    st.caption(f"Model: {MODEL_NAME} · metrics on port {METRICS_PORT} at /metrics")

tab1, tab2 = st.tabs(["🖼️ Single image", "🗂️ Bulk (ZIP)"])
with tab1:
    st.markdown("**Caption one picture.** Accepted: JPG, PNG, BMP, WEBP.")
    f = st.file_uploader("Choose an image", type=["jpg", "jpeg", "png", "bmp", "webp"], key="s")
    if f and st.button("Caption", key="bs", type="primary"):
        run_single(f, sid, ip)
with tab2:
    st.markdown(
        f"**Caption many pictures at once.** Put your images in a ZIP file (up to {MAX_ZIP_IMAGES}). "
        "They are processed one by one, and you can watch the CPU rise on the dashboard."
    )
    z = st.file_uploader("Choose a ZIP file", type=["zip"], key="b")
    if z and st.button("Caption all", key="bb", type="primary"):
        run_bulk(z, sid, ip)
