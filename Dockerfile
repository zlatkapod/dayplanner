
# Simple dev-friendly container
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expose Flask on port 8383
EXPOSE 8383

# Declare a mount point for persistent data
VOLUME ["/app/data"]

ENV PYTHONUNBUFFERED=1
CMD ["python", "app.py"]

