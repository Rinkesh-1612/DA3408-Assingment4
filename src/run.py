"""Container entry point. Start /metrics when the container starts, not at the first page visit. Then start Streamlit."""
import os
import sys

import metrics

metrics.start(int(os.getenv("METRICS_PORT", "28000")), "Salesforce/blip-image-captioning-base")
from streamlit.web import cli  # noqa: E402

sys.argv = ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
cli.main()
