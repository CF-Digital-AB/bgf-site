FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=5000 \
    BGF_DB=/data/survey.db

WORKDIR /app

# System libraries required by WeasyPrint (PDF generation)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libpangoft2-1.0-0 \
        libharfbuzz-subset0 \
        libfreetype6 \
        fontconfig \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py generate_pdf.py index.html ./
COPY templates/ templates/
COPY static/ static/

# SQLite database lives on a volume so data survives container rebuilds.
VOLUME ["/data"]
EXPOSE 5000

CMD ["python", "app.py"]
