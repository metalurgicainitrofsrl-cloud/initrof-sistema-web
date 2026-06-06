FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV INITROF_DATA_DIR=/app/data

WORKDIR /app

COPY requirements-web.txt /app/requirements-web.txt
RUN pip install --no-cache-dir -r /app/requirements-web.txt

COPY initrof_app /app/initrof_app
COPY initrof_web /app/initrof_web
COPY resources /app/resources

RUN mkdir -p /app/data

EXPOSE 8000

CMD ["uvicorn", "initrof_web.app:app", "--host", "0.0.0.0", "--port", "8000"]
