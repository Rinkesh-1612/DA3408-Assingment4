FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 HF_HOME=/cache/hf
WORKDIR /app
COPY requirements.txt .
# Install torch for CPU from the PyTorch CPU index. Install all other packages from PyPI. All versions are fixed.
RUN pip install --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple -r requirements.txt
COPY src/ ./
EXPOSE 8501 28000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request as u;u.urlopen('http://localhost:8501/_stcore/health')" || exit 1
CMD ["python", "run.py"]
