FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    cron tini && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY oura_sync.py .
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

ENTRYPOINT ["/usr/bin/tini", "--", "./entrypoint.sh"]
