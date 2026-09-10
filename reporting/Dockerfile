FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MPLBACKEND=Agg

WORKDIR /app

COPY requirements.txt .

RUN pip install \
    --no-cache-dir \
    --disable-pip-version-check \
    -r requirements.txt

COPY app.py .
COPY scheduler.py .
COPY influx.py .
COPY entrypoint.sh .

RUN chmod +x /app/entrypoint.sh \
    && mkdir -p /data/reports

EXPOSE 8080

ENTRYPOINT ["/app/entrypoint.sh"]
