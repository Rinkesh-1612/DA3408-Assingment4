"""Make the file dashboards/captioning.json. Run it again after each change: python3 scripts/gen_dashboard.py"""
import json
from pathlib import Path

BLUE, ORANGE, GREEN, VERM, SKY, PURPLE = "#0072B2", "#E69F00", "#009E73", "#D55E00", "#56B4E9", "#CC79A7"
DS = {"type": "prometheus", "uid": "prom"}
panels, _id, _y = [], 0, 0


def nid():
    global _id
    _id += 1
    return _id


def tgt(expr, legend, ref="A", instant=False):
    t = {"datasource": DS, "expr": expr, "legendFormat": legend, "refId": ref}
    if instant:
        t.update(instant=True, range=False, format="table")
    return t


def row(title):
    global _y
    panels.append({"id": nid(), "type": "row", "title": title, "collapsed": False,
                   "gridPos": {"x": 0, "y": _y, "w": 24, "h": 1}, "panels": []})
    _y += 1


POINT_SIZES = (5, 8, 11)  # Each series has its own marker size. The series stay clear in print and in grey tones.
LINE_STYLES = ({"fill": "solid"}, {"fill": "dash", "dash": [10, 8]}, {"fill": "dot", "dash": [0, 10]})


def story(text):
    """Add one line of text under a row title. The reader sees what the row shows without a mouse hover."""
    global _y
    panels.append({"id": nid(), "type": "text", "title": "", "transparent": True,
                   "gridPos": {"x": 0, "y": _y, "w": 24, "h": 2},
                   "options": {"mode": "markdown", "content": f"**The story:** {text}"}})
    _y += 2


def ts(title, desc, targets, x, w, h, unit, ylabel, colors, scale="linear", y_axis_right=None,
       minv=None, maxv=None):
    """Add a time series panel. The panel always shows markers. Each series has its own line style (solid, dash or dot).
    The series stay clear in print and in grey tones."""
    ov = []
    for i, (t, c) in enumerate(zip(targets, colors)):
        ov.append({"matcher": {"id": "byFrameRefID", "options": t["refId"]}, "properties": [
            {"id": "color", "value": {"mode": "fixed", "fixedColor": c}},
            {"id": "custom.lineStyle", "value": LINE_STYLES[i % len(LINE_STYLES)]},
            {"id": "custom.pointSize", "value": POINT_SIZES[i % len(POINT_SIZES)]},
        ]})
    for ref, side in (y_axis_right or {}).items():
        for o in ov:
            if o["matcher"]["options"] == ref:
                o["properties"] += [{"id": "custom.axisPlacement", "value": "right"},
                                    {"id": "unit", "value": side["unit"]},
                                    {"id": "custom.axisLabel", "value": side["label"] + " · linear"}]
    custom = {"drawStyle": "line", "lineWidth": 2, "showPoints": "always", "pointSize": 6,
              "fillOpacity": 8, "spanNulls": True,
              "axisLabel": ylabel if scale == "log" else ylabel + " · linear",
              "scaleDistribution": {"type": "log", "log": 2} if scale == "log" else {"type": "linear"}}
    defaults = {"unit": unit, "custom": custom, "color": {"mode": "palette-classic"}}
    if minv is not None: defaults["min"] = minv
    if maxv is not None: defaults["max"] = maxv
    global _y
    panels.append({"id": nid(), "type": "timeseries", "title": title,
                   "description": desc + f" Y-axis scale: {scale}.", "datasource": DS,
                   "gridPos": {"x": x, "y": _y, "w": w, "h": h}, "targets": targets,
                   "fieldConfig": {"defaults": defaults, "overrides": ov},
                   "options": {"legend": {"displayMode": "table", "placement": "bottom", "calcs": ["lastNotNull", "max"]},
                               "tooltip": {"mode": "multi"}}})


def stat(title, desc, expr, x, w, mapping=None, unit="none", colors=None):
    global _y
    thr = {"mode": "absolute", "steps": colors or [{"color": BLUE, "value": None}]}
    panels.append({"id": nid(), "type": "stat", "title": title, "description": desc, "datasource": DS,
                   "gridPos": {"x": x, "y": _y, "w": w, "h": 4},
                   "targets": [tgt(expr, "")],
                   "fieldConfig": {"defaults": {"unit": unit, "mappings": mapping or [], "thresholds": thr,
                                                "color": {"mode": "thresholds"}}, "overrides": []},
                   "options": {"colorMode": "background", "graphMode": "none", "textMode": "value"}})


def updown():
    return [{"type": "value", "options": {"1": {"text": "▲ UP", "color": BLUE},
                                          "0": {"text": "▼ DOWN", "color": VERM}}}]


UPD = [{"color": VERM, "value": None}, {"color": BLUE, "value": 1}]
CPU = '100 - avg(rate(node_cpu_seconds_total{mode="idle"}[30s])) * 100'

# ---------------------------------------------------------------- Row 1: health
row("1 · Health — is everything alive?")
story('all tiles should be blue. If the app or node exporter turns orange-red, nothing below can be trusted. “No data” on Success ratio or Last request only means no traffic yet.')
stat("Captioning app", "UP/DOWN of the app's /metrics endpoint (port 28000). Blue = up, orange-red = down; text label also shown.",
     'up{job="captioning-app"}', 0, 3, updown(), colors=UPD)
stat("Node exporter", "UP/DOWN of node_exporter (port 9100), the source of host CPU/RAM/disk data.",
     'up{job="node"}', 3, 3, updown(), colors=UPD)
stat("Model loaded", "1 once the BLIP model is resident in memory.",
     "caption_model_loaded", 6, 3, [{"type": "value", "options": {"1": {"text": "LOADED", "color": BLUE},
                                                                   "0": {"text": "NOT LOADED", "color": VERM}}}], colors=UPD)
stat("Model load time", "Seconds the app took to load BLIP at start-up (gauge caption_model_load_seconds). Cold start cost.",
     "caption_model_load_seconds", 9, 3, unit="s", colors=[{"color": BLUE, "value": None}, {"color": ORANGE, "value": 60}])
stat("Active requests", "Requests currently being served (single + bulk). Spikes mean the CPU is busy.",
     "sum(caption_active_requests)", 12, 3, colors=[{"color": BLUE, "value": None}, {"color": ORANGE, "value": 2}])
stat("Success ratio (5 m)", "Share of images captioned without error over the last 5 minutes. 'No data' = no traffic in that window.",
     'sum(rate(caption_images_processed_total{status="success"}[5m])) / (sum(rate(caption_images_processed_total[5m])) > 0)',
     15, 3, unit="percentunit", colors=[{"color": VERM, "value": None}, {"color": ORANGE, "value": 0.9}, {"color": BLUE, "value": 0.99}])
stat("Last request", "Time since the last user request (gauge caption_last_request_timestamp_seconds). Large = app idle; No data = no request since start.",
     "time() - (caption_last_request_timestamp_seconds > 0)", 18, 3, unit="s")
stat("Firing alerts", "Number of Prometheus alerts currently firing (rules in alert_rules.yml). Details in the table at the bottom.",
     'count(ALERTS{alertstate="firing"}) or vector(0)', 21, 3, colors=[{"color": BLUE, "value": None}, {"color": VERM, "value": 1}])
_y += 4

# ---------------------------------------------------------------- Row 2: throughput
row("2 · Throughput — how much work is done?")
story('Single (solid) is occasional; Bulk (dashed) arrives in bursts of images per second. The Errors panel stays empty while the app is healthy.')
ts("Throughput · images per second", "Images captioned per second, split by Single vs Bulk mode (1-minute rate). Bulk bursts dominate.",
   [tgt('sum by (mode) (rate(caption_images_processed_total{status="success"}[1m]))', "{{mode}}")],
   0, 8, 8, "ops", "images / s", [BLUE])
ts("Requests · by mode", "User requests (button clicks) per minute for each mode; one bulk request contains many images.",
   [tgt('sum by (mode) (rate(caption_requests_total[1m])) * 60', "{{mode}}")],
   8, 8, 8, "none", "requests / min", [ORANGE])
ts("Errors · by type", "Errors per minute by type (bad image, bad zip, inference, size limit). Flat at zero is healthy.",
   [tgt('sum by (error_type) (rate(caption_errors_total[1m])) * 60', "{{error_type}}")],
   16, 8, 8, "none", "errors / min", [VERM], minv=0)
_y += 8

# ---------------------------------------------------------------- Row 3: latency
row("3 · Latency — how long does each image take?")
story('on a CPU one image takes seconds, not milliseconds. The gap between p50 and p99 shows the slow tail; the HighInferenceLatencyP95 alert fires when p95 passes 10 s.')
ts("Inference latency · percentiles (log scale)", "p50 / p95 / p99 model inference time per image, all modes (1-minute window). Log₂ axis so tails stay visible.",
   [tgt('histogram_quantile(0.50, sum by (le) (rate(caption_inference_seconds_bucket[1m])))', "p50", "A"),
    tgt('histogram_quantile(0.95, sum by (le) (rate(caption_inference_seconds_bucket[1m])))', "p95", "B"),
    tgt('histogram_quantile(0.99, sum by (le) (rate(caption_inference_seconds_bucket[1m])))', "p99", "C")],
   0, 8, 8, "s", "seconds per image (log₂)", [BLUE, ORANGE, VERM], scale="log")
ts("Mean inference time · by mode", "Average seconds per image computed from the histogram _sum/_count, Single vs Bulk.",
   [tgt('sum by (mode) (rate(caption_inference_seconds_sum[1m])) / clamp_min(sum by (mode) (rate(caption_inference_seconds_count[1m])), 1e-9)', "{{mode}}")],
   8, 8, 8, "s", "seconds per image", [BLUE, ORANGE], minv=0)
ts("Request latency p95 · end to end", "95th-percentile wall time of a whole request (upload→result). Bulk is much longer than Single by design.",
   [tgt('histogram_quantile(0.95, sum by (le, mode) (rate(caption_request_seconds_bucket[2m])))', "{{mode}}")],
   16, 8, 8, "s", "seconds per request", [BLUE, ORANGE], minv=0)
_y += 8

# ---------------------------------------------------------------- Row 4: payload & pipeline


def mean(metric, win="1m", by=""):
    """Return the mean value of each observation. Use the _sum and _count of a histogram or summary."""
    g = f" by ({by})" if by else ""
    return (f"sum{g} (rate({metric}_sum[{win}])) / "
            f"clamp_min(sum{g} (rate({metric}_count[{win}])), 1e-9)")


row("4 · Payload & pipeline — what goes in, where the time goes")
story('model inference is about 100× slower than decoding and resizing (log axis), so the CPU-bound model, not I/O, is the bottleneck.')
ts("Pipeline stages · preprocess vs inference", "Mean seconds per image spent decoding/resizing vs running BLIP (histogram _sum/_count). Inference dominates by ~100×, hence the log₂ axis.",
   [tgt(mean("caption_preprocess_seconds"), "preprocess (decode + resize)", "A"),
    tgt(mean("caption_inference_seconds"), "model inference", "B")],
   0, 6, 8, "s", "seconds per image (log₂)", [SKY, VERM], scale="log")
ts("Caption length · words (Summary)", "Mean words per generated caption, Single vs Bulk, from the Summary's _sum/_count. A sudden drop would hint at degenerate output.",
   [tgt(mean("caption_words", by="mode"), "{{mode}}")],
   6, 6, 8, "none", "words per caption", [BLUE, ORANGE], minv=0)
ts("Upload payload · image size and bandwidth", "Left: mean uploaded image size (Summary caption_image_size_bytes). Right: upload bandwidth from the caption_upload_bytes_total counter.",
   [tgt(mean("caption_image_size_bytes"), "mean image size (bytes)", "A"),
    tgt("sum(rate(caption_upload_bytes_total[1m]))", "upload bandwidth (B/s)", "B")],
   12, 6, 8, "bytes", "bytes per image", [GREEN, PURPLE], y_axis_right={"B": {"unit": "Bps", "label": "upload (bytes/s)"}}, minv=0)
ts("Bulk jobs · batch size, ZIP size, skipped entries", "Mean images per bulk request (histogram) and mean ZIP size (Summary), plus ZIP entries skipped per 5 min (dirs, non-images, over limit). 5-minute window because bulk jobs are rare.",
   [tgt(mean("caption_batch_size_images", "5m"), "mean images per ZIP", "A"),
    tgt("sum(increase(caption_zip_entries_skipped_total[5m]))", "entries skipped (per 5 min)", "B"),
    tgt(mean("caption_zip_size_bytes", "5m"), "mean ZIP size (bytes)", "C")],
   18, 6, 8, "none", "images / entries", [BLUE, ORANGE, GREEN], y_axis_right={"C": {"unit": "bytes", "label": "ZIP size (bytes)"}}, minv=0)
_y += 8

# ---------------------------------------------------------------- Row 5: resources
row("5 · System resources — what does the hardware feel?")
story('host CPU and app CPU (both as % of all cores) rise together during inference; app memory steps up once when the model loads and then stays flat.')
ts("Host CPU · utilisation", "Whole-machine CPU busy % from node_exporter vs. the app process alone, both as a share of all cores so they are comparable. Right: app thread count (torch spawns workers during inference).",
   [tgt(CPU, "host CPU (all cores)", "A"), tgt('caption_process_cpu_percent / scalar(count(count by (cpu) (node_cpu_seconds_total{mode="idle"})))', "app process (% of all cores)", "B"),
    tgt("caption_process_threads", "app threads", "C")],
   0, 8, 8, "percent", "CPU %", [BLUE, ORANGE, GREEN], y_axis_right={"C": {"unit": "none", "label": "threads"}}, minv=0)
ts("Memory · host and app", "Host RAM in use (%, left) vs. app resident memory (GiB, right axis).",
   [tgt("(1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100", "host RAM used (%)", "A"),
    tgt("caption_process_rss_bytes", "app RSS (bytes)", "B")],
   8, 8, 8, "percent", "host RAM used (%)", [BLUE, ORANGE], y_axis_right={"B": {"unit": "bytes", "label": "app RSS (bytes)"}}, minv=0)
ts("Disk · usage and I/O", "Root disk used % (left) and host disk write rate (right, bytes/s). Model/ZIP temp files show up as write bursts.",
   [tgt('(1 - node_filesystem_avail_bytes{mountpoint="/",fstype!="tmpfs"} / node_filesystem_size_bytes{mountpoint="/",fstype!="tmpfs"}) * 100', "root disk used (%)", "A"),
    tgt('sum(rate(node_disk_written_bytes_total{device!~"loop.*|ram.*|dm-.*"}[30s]))', "disk writes (B/s)", "B")],
   16, 8, 8, "percent", "disk used (%)", [GREEN, PURPLE], y_axis_right={"B": {"unit": "Bps", "label": "disk writes (bytes/s)"}}, minv=0)
_y += 8

# ---------------------------------------------------------------- Row 6: correlation
row("6 · Correlation — application spikes vs hardware")
story('when a bulk job starts, “images remaining” jumps to N; host CPU climbs and stays high until it counts down to 0, and the load average follows. This is the app-to-hardware link.')
ts("Bulk upload vs host CPU", "Left: host CPU %. Right: images remaining in the active bulk job. CPU climbs when a bulk job starts and falls as the backlog drains.",
   [tgt(CPU, "host CPU (%)", "A"), tgt("caption_bulk_images_remaining", "bulk images remaining", "B")],
   0, 12, 9, "percent", "host CPU (%)", [BLUE, VERM], y_axis_right={"B": {"unit": "none", "label": "images remaining"}}, minv=0)
ts("Throughput vs CPU load", "Left: images/s processed. Right: 1-minute load average. Throughput plateaus once CPU saturates — more load only raises latency.",
   [tgt('sum(rate(caption_images_processed_total{status="success"}[1m]))', "images / s", "A"),
    tgt("node_load1", "load average (1 m)", "B")],
   12, 12, 9, "ops", "images / s", [GREEN, ORANGE], y_axis_right={"B": {"unit": "none", "label": "load avg (1 m)"}}, minv=0)
_y += 9

def table(title, desc, expr, x, w, rename, exclude=()):
    hide = {"Time": True, **{k: True for k in exclude}}
    panels.append({"id": nid(), "type": "table", "title": title, "description": desc,
                   "datasource": DS, "gridPos": {"x": x, "y": _y, "w": w, "h": 7},
                   "targets": [tgt(expr, "", instant=True)],
                   "transformations": [{"id": "organize", "options": {"excludeByName": hide, "renameByName": rename}}],
                   "fieldConfig": {"defaults": {"unit": "none", "decimals": 0}, "overrides": []}})


row("7 · Who is using it, what is running, what is wrong? (metadata)")
story('who is sending the load (session and source IP), which alerts are firing right now, and which model and device are serving requests.')
table("Top clients · images processed (since app start)",
      "Images captioned per session id / source IP, Single vs Bulk, from the counter's current value (cumulative since the app started). Shows who drives the load.",
      'topk(10, sum by (client_id, client_ip, mode) (caption_images_processed_total{status="success"}))', 0, 12,
      {"client_id": "Session ID", "client_ip": "Source IP", "mode": "Mode", "Value": "Images (total)"})
table("Firing alerts · details", "Alerts currently firing in Prometheus (alert_rules.yml), also routed to Alertmanager on :9093. Empty = healthy.",
      'ALERTS{alertstate="firing"}', 12, 7,
      {"alertname": "Alert", "severity": "Severity"}, exclude=("__name__", "alertstate", "Value", "instance", "job", "service"))
table("Running model · app info", "Static build info from the Info metric caption_app_info: which model, framework and device serve requests.",
      "caption_app_info", 19, 5, {"model": "Model", "framework": "Framework", "device": "Device"},
      exclude=("__name__", "Value", "instance", "job", "service"))

# Set colour and line style for each series name (single or bulk). Do not set them for each query.
for p in panels:
    if p["type"] == "timeseries" and len(p["targets"]) == 1 and p["targets"][0]["legendFormat"] == "{{mode}}":
        p["fieldConfig"]["overrides"] = [
            {"matcher": {"id": "byName", "options": n}, "properties": [
                {"id": "color", "value": {"mode": "fixed", "fixedColor": c}},
                {"id": "custom.lineStyle", "value": {"fill": f, "dash": [10, 8]}}]}
            for n, c, f in (("single", BLUE, "solid"), ("bulk", ORANGE, "dash"))]

dash = {"uid": "captioning-obs", "title": "Image Captioning · Observability",
        "description": "Top→bottom: health, throughput, latency, payload & pipeline, hardware, correlation, metadata. Palette: Okabe-Ito (colour-blind safe); markers + dash styles distinguish series without colour.",
        "tags": ["DA3408", "prometheus"], "timezone": "browser", "refresh": "5s", "schemaVersion": 39,
        "time": {"from": "now-15m", "to": "now"}, "panels": panels, "templating": {"list": []},
        "annotations": {"list": []}, "editable": True}
with open(Path(__file__).resolve().parent.parent / "dashboards" / "captioning.json", "w") as f:
    json.dump(dash, f, indent=2)
print("panels:", len(panels))
