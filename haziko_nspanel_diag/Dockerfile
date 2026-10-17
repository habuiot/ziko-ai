FROM python:3.12.12-slim-bookworm
WORKDIR /app
COPY probe.py /app/probe.py
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
CMD ["python", "-u", "/app/probe.py"]
