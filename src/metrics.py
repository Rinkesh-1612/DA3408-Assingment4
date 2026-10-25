"""All Prometheus metrics of the app. Python imports this file one time for each process."""
import os
import threading
import time

import psutil
from prometheus_client import Counter, Gauge, Histogram, Info, Summary, start_http_server

NS = "caption"
MODES = ("single", "bulk")

# ---- Counters: values that only increase -----------------------------------
IMAGES = Counter(f"{NS}_images_processed", "Images processed, by mode/status/client",
                 ["mode", "status", "client_id", "client_ip"])
REQUESTS = Counter(f"{NS}_requests", "User requests received", ["mode", "client_id"])
ERRORS = Counter(f"{NS}_errors", "Errors by mode and type", ["mode", "error_type"])
BYTES_IN = Counter(f"{NS}_upload_bytes", "Bytes uploaded", ["mode"])
SKIPPED = Counter(f"{NS}_zip_entries_skipped", "ZIP entries skipped", ["reason"])

# ---- Histograms: values in time buckets ------------------------------------
INFERENCE_BUCKETS = (0.1, 0.25, 0.5, 1, 2, 3, 5, 8, 13, 20, 30, 60)
INFERENCE = Histogram(f"{NS}_inference_seconds", "Model inference time per image",
                      ["mode"], buckets=INFERENCE_BUCKETS)
REQUEST_LAT = Histogram(f"{NS}_request_seconds", "End-to-end request time",
                        ["mode"], buckets=(0.5, 1, 2, 5, 10, 20, 40, 80, 160, 320, 640))
BATCH_SIZE = Histogram(f"{NS}_batch_size_images", "Images per bulk request",
                       buckets=(1, 2, 5, 10, 20, 30, 50))
PREPROCESS = Histogram(f"{NS}_preprocess_seconds", "Image decode/resize time",
                       ["mode"], buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1))

# ---- Summaries: give the _sum and _count values ----------------------------
CAPTION_WORDS = Summary(f"{NS}_words", "Words per generated caption", ["mode"])
IMAGE_BYTES = Summary(f"{NS}_image_size_bytes", "Uploaded image size in bytes", ["mode"])
ZIP_BYTES = Summary(f"{NS}_zip_size_bytes", "Uploaded ZIP size in bytes")

# ---- Gauges: values that go up and down ------------------------------------
ACTIVE = Gauge(f"{NS}_active_requests", "Requests currently being served", ["mode"])
BULK_REMAINING = Gauge(f"{NS}_bulk_images_remaining", "Images left in current bulk job")
MODEL_LOADED = Gauge(f"{NS}_model_loaded", "1 if the model is loaded in memory")
MODEL_LOAD_S = Gauge(f"{NS}_model_load_seconds", "Seconds taken to load the model")
LAST_REQ_TS = Gauge(f"{NS}_last_request_timestamp_seconds", "Unix time of last request")
PROC_RSS = Gauge(f"{NS}_process_rss_bytes", "App process resident memory")
PROC_CPU = Gauge(f"{NS}_process_cpu_percent", "App process CPU % (100 = one core)")
PROC_THREADS = Gauge(f"{NS}_process_threads", "App process thread count")
INFO = Info(f"{NS}_app", "Static app/model information")

_proc = psutil.Process(os.getpid())
_started = False
_lock = threading.Lock()


def _sample_process():
    _proc.cpu_percent(None)
    while True:
        PROC_RSS.set(_proc.memory_info().rss)
        PROC_CPU.set(_proc.cpu_percent(None))
        PROC_THREADS.set(_proc.num_threads())
        time.sleep(2)


def start(port: int = 28000, model_name: str = "") -> None:
    """Start the /metrics HTTP server on its own port. It starts one time for each process."""
    global _started
    with _lock:
        if _started:
            return
        for m in MODES:  # Create each series with value 0. Then rate() works from the start.
            ACTIVE.labels(m).set(0)
            INFERENCE.labels(m)
            REQUEST_LAT.labels(m)
            PREPROCESS.labels(m)
            CAPTION_WORDS.labels(m)
            IMAGE_BYTES.labels(m)
            BYTES_IN.labels(m)
        MODEL_LOADED.set(0)
        INFO.info({"model": model_name, "framework": "transformers+torch", "device": "cpu"})
        start_http_server(port)
        threading.Thread(target=_sample_process, daemon=True).start()
        _started = True
