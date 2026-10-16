# Control node image for local runs (no native Ansible on Windows). CI installs the same requirements.
FROM python:3.12-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends openssh-client git \
 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt requirements.yml /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
 && ansible-galaxy collection install -r /tmp/requirements.yml
