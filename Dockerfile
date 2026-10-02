FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production \
    PORT=8080

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Apply database migrations, then serve. Generation requests can take a
# minute, so use threads and a long timeout (match Cloud Run's --timeout).
CMD flask --app wsgi db upgrade && \
    exec gunicorn wsgi:app --bind :$PORT --workers 2 --threads 8 --timeout 300 --access-logfile -
