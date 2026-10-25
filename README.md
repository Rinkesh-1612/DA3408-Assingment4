# DA3408 Assignment 4: Application Monitoring with Prometheus and Grafana

Rinkesh (DA24B017)

**Video of the dashboard (5-second refresh):** [Google Drive link](https://drive.google.com/file/d/101JFvYujwBGKzEWT_fX7mULqh6JcZ5G1/view?usp=drive_link)

This project has one image captioning application. The application runs on a CPU.
The application has a Streamlit interface and the BLIP model.
The application sends its metrics to Prometheus. Node exporter sends the metrics of the machine.
Grafana shows both sets of metrics on one dashboard. Prometheus sends an alert when a value is not normal.
The dashboard shows how a bulk upload changes the CPU and the memory of the machine.

## Contents

```
DA3408-Assignment4/
├── src/                      Application code (copied into the Docker image)
│   ├── app.py                Streamlit app: Single mode and Bulk (ZIP) mode
│   ├── metrics.py            All Prometheus metrics; starts the /metrics server
│   └── run.py                Container entry point: starts /metrics, then Streamlit
├── configs/
│   ├── prometheus/
│   │   ├── prometheus.yml    Scrape config: app (:28000) and node_exporter (:9100)
│   │   ├── alert_rules.yml   The six alert rules
│   │   └── alertmanager.yml  Alertmanager configuration
│   └── grafana/provisioning/ Loads the data source and the dashboard at start
├── dashboards/
│   └── captioning.json       JSON export of the Grafana dashboard
├── scripts/
│   ├── gen_dashboard.py      Makes dashboards/captioning.json
│   └── load_test.py          Makes sample_bulk.zip of test images for Bulk mode
├── games.zip                 Sample ZIP of 12 images for the Bulk mode
├── Dockerfile                App image (Python 3.12, CPU-only PyTorch)
├── docker-compose.yml        App, node_exporter, Prometheus, Alertmanager, Grafana
├── requirements.txt          Python packages with exact versions (used by the Dockerfile)
├── AI_DISCLOSURE.md          The AI tool, what it does, and how the work is checked
├── Makefile                  make up / down / logs / load / dashboard
└── .env.example              Host ports; copy it to .env to change a port
```

## Application

The application uses the model `Salesforce/blip-image-captioning-base` on the CPU.

- **Single mode.** The user uploads one image. The application gives one caption.
- **Bulk mode.** The user uploads a ZIP file. The application gives a table of captions. It processes the images one by one and shows a progress bar.

The application has these limits. They keep the CPU and memory use low:

- A ZIP file can have 50 images at most. The application ignores the extra images.
- A ZIP file can have 100 MB at most.
- The application makes each image smaller (512 pixels on the long side) before inference.
- The application ignores hidden files, folders and files that are not images. It counts them in a metric.

The application does not stop when a file is bad. It counts the error and goes to the next file.

## Metrics

The application sends its metrics at `/metrics` on port 28000. This port is not the Streamlit port.
All metric names start with `caption_`.

| Type | Metric | Labels | Meaning |
|---|---|---|---|
| Counter | `images_processed_total` | `mode`, `status`, `client_id`, `client_ip` | Images processed. |
| Counter | `requests_total` | `mode`, `client_id` | Requests from users. |
| Counter | `errors_total` | `mode`, `error_type` | Errors (bad image, bad ZIP, inference, ZIP too large). |
| Counter | `upload_bytes_total` | `mode` | Bytes uploaded. |
| Counter | `zip_entries_skipped_total` | `reason` | ZIP entries that the application ignores. |
| Gauge | `active_requests` | `mode` | Requests in progress now. |
| Gauge | `bulk_images_remaining` | none | Images that the current bulk job did not do yet. |
| Gauge | `model_loaded` | none | 1 when the model is in memory. |
| Gauge | `model_load_seconds` | none | Time to load the model. |
| Gauge | `last_request_timestamp_seconds` | none | Time of the last request. |
| Gauge | `process_rss_bytes` | none | Memory of the application process. |
| Gauge | `process_cpu_percent` | none | CPU of the application process (100 = one core). |
| Gauge | `process_threads` | none | Threads of the application process. |
| Histogram | `inference_seconds` | `mode` | Model time for each image. |
| Histogram | `request_seconds` | `mode` | Total time for each request. |
| Histogram | `preprocess_seconds` | `mode` | Time to decode and shrink each image. |
| Histogram | `batch_size_images` | none | Images in each bulk request. |
| Summary | `words` | `mode` | Words in each caption (`_sum` and `_count`). |
| Summary | `image_size_bytes` | `mode` | Size of each image (`_sum` and `_count`). |
| Summary | `zip_size_bytes` | none | Size of each ZIP file (`_sum` and `_count`). |
| Info | `app_info` | `model`, `framework`, `device` | Fixed data about the application. |

A Summary gives the values `_sum` and `_count`. The Python client library gives no `_total` suffix for a Summary. The counters in the table end in `_total`.

The label `client_id` is the first 8 characters of the Streamlit session ID.
The label `client_ip` is the source address of the request.
On Linux, Docker keeps the real address of the client. On Docker Desktop (Mac or Windows), `client_ip` shows the address of the Docker network gateway.
Each new session makes a new `client_id` value. Do not use `client_id` on a public service with many users.

## Node exporter

Node exporter runs in its own container.
It reads `/proc` and `/` of the host. The CPU, memory, load and disk values are the values of the machine.
Prometheus scrapes the application and node exporter every 5 seconds.
The dashboard shows both sets of values on the same time axis.

## Alerts

Prometheus calculates these rules. It sends the active alerts to Alertmanager.

| Alert | Condition | Time | Severity |
|---|---|---|---|
| `CaptioningAppDown` | The application target is down. | 15 s | critical |
| `HighInferenceLatencyP95` | The p95 inference time is more than 10 s. | 30 s | warning |
| `HighErrorRatio` | More than 10% of the images fail. | 1 min | warning |
| `HostHighCPU` | The CPU of the host is more than 85%. | 30 s | warning |
| `HostHighMemory` | The memory of the host is more than 90%. | 1 min | critical |
| `HostDiskAlmostFull` | The root disk is more than 90% full. | 2 min | warning |

The column "Time" is the time that the condition must stay true before the alert fires.

Alertmanager has no external receiver.
The active alerts show in Prometheus (`/alerts`), in Alertmanager and on the dashboard.

## Dashboard

The dashboard is **Image Captioning · Observability**. Grafana loads it at start. It refreshes every 5 seconds.
It has 40 panels in seven rows. Each row starts with a line of text, "The story". This line tells what the row shows. Each metric in `src/metrics.py` shows in at least one panel. The rows go from the high-level view to the low-level view:

1. **Health.** Application up or down, node exporter up or down, model loaded, model load time, active requests, success ratio, time since the last request, firing alerts.
2. **Throughput.** Images per second, requests per minute and errors per minute.
3. **Latency.** The p50, p95 and p99 of the inference time, the mean inference time and the p95 of the request time.
4. **Payload and pipeline.** Preprocess time and inference time, words per caption (Summary), image size (Summary) and upload bandwidth, bulk jobs (batch size, ZIP size, skipped entries).
5. **System resources.** Host CPU with the application CPU and threads, host memory with the application memory, disk use and disk writes.
6. **Correlation.** Host CPU with the images that remain in a bulk job. Throughput with the load average.
7. **Metadata.** A table of the images processed for each session and source address, a table of the firing alerts, and the model information.

The dashboard follows the seven commandments of plotting:

| Commandment | How the dashboard follows it |
|---|---|
| Inclusive colors | The colors are the Okabe-Ito colors. People with color blindness can tell them apart. |
| Markers for all media | All lines have markers. The series in one panel have different line styles (solid, dashed, dotted) and different marker sizes. The series are different in black and white. |
| Axes with names | Each axis has a name, a unit and a scale, for example "seconds per image · linear" or "(log₂)". |
| Scale and units | Each panel description gives the scale. The percentile panel and the pipeline-stage panel use a log scale (base 2). The other panels use a linear scale. |
| Legend | Each panel with more than one variable has a legend. The legend shows the last value and the maximum value. |
| Title and sub-title | Each panel has a short title. The sub-title is in the title or in the description. |
| Description | Each row has a visible line of text. Each panel has a longer description (the (i) icon). |

## How to run

### Requirements

- Docker with Docker Compose v2 (check with `docker compose version`).
- Free host ports 8501, 3000, 9090, 9093 and 28000. If a port is in use, read "Change a port" below.
- To run the stack on a remote server, read "Run on a remote server" below. The links in step 4 use `localhost`.
- About 5 GB of free disk space (the image and the model). An Internet connection for the first start.
- Python 3 and `pip` on the host. You need them only for the optional test ZIP file in step 5.

The application does not need a Python environment. The Docker image has all the packages.

### Steps

1. Get the project. Go to its folder:

   ```bash
   git clone <repository-url>
   cd DA3408-Assignment4
   ```

2. Start the stack (or run `make up`):

   ```bash
   docker compose up -d --build
   ```

   The first start builds the image and downloads the model (about 1 GB). This takes some minutes.
   Docker keeps the model in a volume. The next starts are fast.

3. Make sure that all services run and all targets are up:

   ```bash
   docker compose ps
   curl -s localhost:9090/api/v1/targets | grep -o '"health":"[a-z]*"'
   ```

   `docker compose ps` must show 5 services in the state `running`.
   The second command must print `"health":"up"` three times (`captioning-app`, `node`, `prometheus`).
   If a target is down, wait 10 seconds. Then run the command again.

4. Open the application and the dashboard:

   | Service | URL |
   |---|---|
   | Streamlit application | http://localhost:8501 |
   | Grafana (user `admin`, password `admin`) | http://localhost:3000 |
   | Prometheus | http://localhost:9090 |
   | Alertmanager | http://localhost:9093 |
   | Metrics of the application | http://localhost:28000/metrics |

   Use `http://` for these links. Do not use `https://`. The services have no TLS. The browser shows the error `ERR_SSL_PROTOCOL_ERROR` for an `https://` link.
   If your browser changes the link to `https://`, type the complete `http://...` address, or use a private window.

   In Grafana, open **Dashboards**. Then open **Image Captioning · Observability**.
   The dashboard refreshes every 5 seconds. If the refresh is not 5 seconds, select 5s in the refresh list.

5. Make some load. The project has a sample ZIP file, `games.zip`, with 12 images. Use it as the default for the Bulk mode.
   In the application:
   - Upload one image from `games.zip` (or any image) in the **Single image** tab. Select **Caption**.
   - Upload `games.zip` in the **Bulk (ZIP)** tab. Select **Caption all**.

   If you use a remote server, copy `games.zip` to your own computer first. The browser uploads files from the computer that runs the browser.

   For a longer bulk job, make a test ZIP file with 20 images (or run `make load`):

   ```bash
   pip install pillow
   python3 scripts/load_test.py 20
   ```

   The script writes `sample_bulk.zip`. You can also use your own images. A ZIP file can have 50 images at most.

6. Look at the dashboard while the bulk job runs. You see these changes:
   - **Active requests** and **bulk images remaining** increase. Then they decrease.
   - **Host CPU** and **app process CPU** increase.
   - **Images per second** and **inference latency** change.

7. Check the metrics from the command line (optional):

   ```bash
   curl -s localhost:28000/metrics | grep "^caption_images_processed_total"
   curl -s localhost:9090/api/v1/alerts
   ```

8. Stop the stack (or run `make down`):

   ```bash
   docker compose down
   ```

   To delete the model and the Prometheus data also, use `docker compose down -v`.
   After `-v`, the next start downloads the model again.

### Run on a remote server (VPS) and open it from another computer

`localhost` always means the computer of the browser. If the stack runs on a server, `localhost` in the browser of your laptop does not work.
There are two ways to reach the server.

**Option 1. Use the server address.** Replace `localhost` with the IP address of the server, for example `http://<server-ip>:8501`.
Docker opens the ports on all interfaces by default. You must only allow these TCP ports in the firewall.
Change the firewall of the server (for example `ufw allow 8501,3000,9090,9093,28000/tcp`) and the firewall or security group of the cloud provider:

| Port | Service |
|---|---|
| 8501 | Streamlit application |
| 3000 | Grafana |
| 9090 | Prometheus |
| 9093 | Alertmanager |
| 28000 | Metrics of the application |

**Option 2. SSH tunnel (no firewall change).** Run this command on your laptop. Then use the normal `localhost` links:

```bash
ssh -L 8501:localhost:8501 -L 3000:localhost:3000 -L 9090:localhost:9090 -L 9093:localhost:9093 -L 28000:localhost:28000 <user>@<server-ip>
```

In VS Code Remote-SSH, the **Ports** tab can forward the same ports.

**Security on a public server.** Prometheus, Alertmanager and the application have no login. Grafana uses `admin` / `admin` by default.
Before you open the ports to the Internet, set a Grafana password in `.env` (`GRAFANA_ADMIN_PASSWORD=...`). Or use the tunnel and keep the ports closed.
To make the stack private to the server, set `BIND_ADDR=127.0.0.1` in `.env`. Then use the tunnel.
If you change a setting in `.env`, run `docker compose up -d` again.

### Make commands

| Command | Action |
|---|---|
| `make up` | Builds the image and starts the stack. |
| `make logs` | Shows the log of the application. |
| `make load` | Makes `sample_bulk.zip` with 20 images (a longer test than `games.zip`). |
| `make dashboard` | Makes the dashboard JSON again and restarts Grafana. |
| `make down` | Stops the stack. |

### Change a port

If a host port is in use, copy the settings file. Then change the port:

```bash
cp .env.example .env
# Edit .env, for example: GRAFANA_PORT=3001
docker compose up -d
```

The variables are `APP_PORT`, `APP_METRICS_PORT`, `PROMETHEUS_PORT`, `ALERTMANAGER_PORT`, `GRAFANA_PORT`, `BIND_ADDR` and `GRAFANA_ADMIN_PASSWORD`.
Use the new port in the URLs.

### Make the dashboard JSON again

A script makes the file `dashboards/captioning.json`. To change the dashboard, edit `scripts/gen_dashboard.py`. Then run (or run `make dashboard`):

```bash
python3 scripts/gen_dashboard.py
docker compose restart grafana
```

The script uses only the Python standard library.

### Problems

| Problem | Action |
|---|---|
| The page does not load after a start. | The application loads the model. Wait about 30 seconds. Refresh the page. |
| A target is down in `/targets`. | Wait 10 seconds. If the target stays down, run `docker compose logs app` or `docker compose logs node_exporter`. |
| `port is already allocated` or `address already in use` | Change the port (see "Change a port"). |
| Each image takes a long time. | The time depends on the CPU. On a busy machine, one image can take more than 20 seconds. Use fewer and smaller images. |
| The Grafana panels are empty. | Do a Single upload and a Bulk upload first. Some panels show data only after traffic. The panel **Errors by type** stays empty when there are no errors. |

**Notes:**

- Linux is the reference platform. On Docker Desktop (Mac or Windows), the system metrics show the Docker virtual machine and not the host.
- The Dockerfile uses the exact versions in `requirements.txt`. A new build gives the same packages.

## Result

The test used the Single mode and the Bulk mode on a Linux server. These results are from the test:

- The three Prometheus targets were up.
- The Single mode and the Bulk mode both gave captions.
- When a bulk job started, the host CPU increased and the number of remaining images decreased. The memory and the disk writes of the machine also changed. This shows the link between the application and the hardware.
- The alert `HighInferenceLatencyP95` became active during a bulk job. This shows that the alert pipeline works.

## AI usage

Read [AI_DISCLOSURE.md](AI_DISCLOSURE.md).
