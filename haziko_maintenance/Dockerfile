FROM python:3.12.12-slim-bookworm
WORKDIR /srv
COPY server.py /srv/server.py
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
EXPOSE 8096
CMD ["python", "-u", "/srv/server.py"]
