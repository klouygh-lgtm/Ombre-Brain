# Ombre Brain Docker Build
FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (leverage Docker cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn

# Copy entire project
COPY . .
RUN chmod +x scripts/*.sh 2>/dev/null || true

# Persistent mount point
VOLUME ["/app/buckets"]

ENV OMBRE_TRANSPORT=streamable-http
ENV OMBRE_BUCKETS_DIR=/app/buckets

EXPOSE 8000

CMD ["python", "server.py"]