FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_ENDPOINT=https://hf-mirror.com

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
# 模型在构建期下载（约 306 MB）；想放到卷里可注释掉这行、改为启动时执行
RUN python scripts/fetch_models.py

EXPOSE 8000
CMD ["python", "server.py", "--host", "0.0.0.0", "--port", "8000"]
