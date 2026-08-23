# Coverage Gap Finder - runs on the Python base image with nothing added,
# because the app has no third-party dependencies.
FROM python:3.12-slim

WORKDIR /app
COPY . /app

# Leads live on a mounted volume so a redeploy never destroys the database.
ENV LEADS_DB=/data/leads.db
VOLUME ["/data"]

RUN useradd --create-home --uid 10001 app \
 && mkdir -p /data && chown -R app:app /app /data
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s \
  CMD python3 -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/healthz',timeout=3)"

# 0.0.0.0 is correct inside a container - the platform's proxy terminates TLS.
CMD ["python3", "server.py", "--host", "0.0.0.0", "--port", "8000"]
