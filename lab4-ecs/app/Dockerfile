# syntax=docker/dockerfile:1
# Base image from the public ECR gallery (no Docker Hub rate limits in CodeBuild).
FROM public.ecr.aws/docker/library/python:3.12-slim

# Build-time value → runtime env var. CodeBuild passes --build-arg APP_VERSION=v<build number>.
# AWS_EC2_METADATA_DISABLED: this app must never borrow the host's identity; only an explicit task role counts.
ARG APP_VERSION=dev
ENV APP_VERSION=$APP_VERSION \
    PORT=8080 \
    PYTHONUNBUFFERED=1 \
    AWS_EC2_METADATA_DISABLED=true

# Metadata travels with the image: `docker inspect` shows it, so does ECR.
LABEL org.opencontainers.image.title="mission-control" \
      org.opencontainers.image.version=$APP_VERSION

# One OS package (curl: for the health check, and for you when you get a shell inside).
# Update, install and clean the apt cache in ONE layer; a separate RUN would bake the cache into the image forever.
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .

# Run as a non-root user: a compromised web app should not own the container.
RUN useradd --system --no-create-home mission && chown -R mission /app
USER mission

EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s --retries=3 CMD curl -fsS http://127.0.0.1:8080/health || exit 1
CMD ["python", "app.py"]
