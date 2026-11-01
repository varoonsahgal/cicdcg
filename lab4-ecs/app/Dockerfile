# syntax=docker/dockerfile:1
# Base image from the public ECR gallery (no Docker Hub rate limits in CodeBuild).
FROM public.ecr.aws/docker/library/python:3.12-slim

# Build-time value → runtime env var. CodeBuild passes --build-arg APP_VERSION=v<build number>.
ARG APP_VERSION=dev
ENV APP_VERSION=$APP_VERSION \
    PORT=8080 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .

# Run as a non-root user: a compromised web app should not own the container.
RUN useradd --system --no-create-home mission && chown -R mission /app
USER mission

EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=3s --retries=3 CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=2).status==200 else 1)"
CMD ["python", "app.py"]
