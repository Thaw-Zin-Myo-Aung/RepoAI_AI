# Multi-tool production image for RepoAI
# - Python app (uvicorn) for the API server
# - OpenJDK 17 + Maven for Java validation
# - Gradle (binary) for Gradle-based projects

FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive

# Install OS-level build tools, Java and Maven, plus utilities
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       ca-certificates \
       curl \
       unzip \
       git \
       openjdk-17-jdk-headless \
       maven \
    && rm -rf /var/lib/apt/lists/*

# Install Gradle (binary distribution) to /opt
ARG GRADLE_VERSION=8.5.1
RUN curl -fsSL "https://services.gradle.org/distributions/gradle-${GRADLE_VERSION}-bin.zip" -o /tmp/gradle.zip \
    && unzip /tmp/gradle.zip -d /opt \
    && rm /tmp/gradle.zip \
    && ln -s /opt/gradle-${GRADLE_VERSION}/bin/gradle /usr/local/bin/gradle

# Workdir and copy entire source (simpler and robust)
WORKDIR /app

# Copy source and entrypoint
COPY . /app
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Install Python dependencies. Prefer requirements.txt if present, otherwise install from pyproject
RUN python -m pip install --upgrade pip setuptools wheel \
    # Install `uv` CLI so `uv run` is available at runtime (preferred runner)
    && pip install --no-cache-dir uv \
    && if [ -f /app/requirements.txt ]; then \
        pip install --no-cache-dir -r /app/requirements.txt; \
    else \
        pip install --no-cache-dir -e /app; \
    fi

# Create a non-root user and give ownership of app directory
RUN useradd --create-home --shell /bin/bash repoai || true \
    && chown -R repoai:repoai /app
USER repoai

ENV PORT=8000
EXPOSE ${PORT}

# Default entrypoint: prefer `uv run` if present, otherwise run `uvicorn`
ENTRYPOINT ["/bin/sh", "/app/entrypoint.sh"]
