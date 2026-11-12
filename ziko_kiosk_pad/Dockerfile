FROM python:3.12-alpine
RUN apk add --no-cache openssl
WORKDIR /app
COPY app.py secure.py index.html /app/
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 ZIKO_DATA_DIR=/data ZIKO_PORT=8096
EXPOSE 8096 8097 8098
CMD ["python3", "/app/app.py"]
