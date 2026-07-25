# syntax=docker/dockerfile:1
# Build from fo-intel repo root:
#   docker build -f api/Dockerfile -t fo-intel-api .
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api ./api
COPY pipeline ./pipeline
COPY data/export ./data/export
COPY data/index ./data/index

ENV APP_HOST=0.0.0.0
ENV APP_PORT=8080
ENV FO_INDEX_DIR=/app/data/index
ENV PYTHONPATH=/app
EXPOSE 8080

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]
