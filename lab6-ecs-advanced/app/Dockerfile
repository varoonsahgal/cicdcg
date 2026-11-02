# syntax=docker/dockerfile:1
# Galactic Pizza. One source tree, four releases: the release is chosen at build time.
#   docker build --build-arg RELEASE=1.2 -t galactic-pizza:1.2 .
FROM public.ecr.aws/docker/library/python:3.12-slim

ARG RELEASE=1.0
ENV RELEASE=$RELEASE \
    PORT=8080 \
    PYTHONUNBUFFERED=1
LABEL org.opencontainers.image.title="galactic-pizza" \
      org.opencontainers.image.version=$RELEASE

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
RUN useradd --system --no-create-home pizza && chown -R pizza /app
USER pizza

EXPOSE 8080
# exec form: python is PID 1 and receives ECS's SIGTERM directly (a shell in between would swallow it).
CMD ["python", "app.py"]
