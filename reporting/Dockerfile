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

COPY *.py ./
COPY entrypoint.sh ./
COPY templates ./templates

RUN chmod +x /app/entrypoint.sh \
    && mkdir -p \
        /data/reports/generated \
        /data/reports/publish_queue \
        /data/reports/published

EXPOSE 8080

ENTRYPOINT ["/app/entrypoint.sh"]
