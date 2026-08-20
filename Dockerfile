FROM python:3.12-slim
ENV TZ=Europe/Vienna
RUN apt-get update && apt-get install -y --no-install-recommends tzdata && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend.py .
RUN mkdir -p /data
ENV PORT=80
ENV STATE_FILE=/data/state.json
EXPOSE 80
CMD ["python", "backend.py"]
