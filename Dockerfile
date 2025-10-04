# Use official lightweight Python image
FROM python:3.11-slim

# Set working directory inside the container
WORKDIR /app

# Copy project files into the container
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port Cloud Run will use
EXPOSE 8080

CMD ["gunicorn", "-b", ":8080", "app:create_app()"]
