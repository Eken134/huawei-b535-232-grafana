# Dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir huawei-lte-api prometheus_client

COPY exporter.py .

ENV ROUTER_ADDRESS=192.168.8.1 \
    PROM_PORT=8080

EXPOSE 8080

CMD ["python", "./exporter.py"]