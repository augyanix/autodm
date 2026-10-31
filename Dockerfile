FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 DB_FILE=/data/autodm.db RULES_FILE=/app/rules.json
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
 && useradd -r -u 10001 app && mkdir /data && chown app /data
COPY app.py rules.json ./
USER app
VOLUME /data
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request as u; u.urlopen('http://localhost:8000/health')"
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--no-server-header", "--limit-concurrency", "50"]
