FROM python:3.12.12-slim-bookworm
WORKDIR /srv
COPY run.py /srv/run.py
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
CMD ["python", "-u", "/srv/run.py"]
