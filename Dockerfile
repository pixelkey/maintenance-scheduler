FROM python:3.11-slim

# Install cron, sudo and procps (for ps command)
RUN apt-get update && \
    apt-get install -y cron sudo procps && \
    rm -rf /var/lib/apt/lists/*

# Create a non-root user with the same UID/GID as the host user
ARG USER_ID=1000
ARG GROUP_ID=1000

# Create or reuse group, then create user
RUN set -ex; \
    group_name=$(getent group ${GROUP_ID} | cut -d: -f1); \
    if [ -z "$group_name" ]; then \
      groupadd -g ${GROUP_ID} appgroup; \
      group_name=appgroup; \
    fi; \
    useradd -u ${USER_ID} -g $group_name -m -s /bin/bash appuser && \
    echo "appuser ALL=(ALL) NOPASSWD: /usr/sbin/cron" >> /etc/sudoers

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ src/
COPY templates/ templates/

# Create necessary directories with proper permissions
RUN mkdir -p \
    data/output \
    data/preview \
    config && \
    touch \
    data/maintenance_scheduler.log \
    data/cron.log \
    data/sent_notifications.json && \
    chown -R appuser:$(getent group ${GROUP_ID} | cut -d: -f1) /app && \
    chmod -R 755 /app && \
    chmod 666 \
    data/maintenance_scheduler.log \
    data/cron.log \
    data/sent_notifications.json

# Set up cron job for the appuser
COPY crontab /tmp/crontab
RUN crontab -u appuser /tmp/crontab && \
    rm /tmp/crontab

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV MOCK_CALENDAR=false

# Create the entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Switch to non-root user
USER appuser

# Use entrypoint script to start both cron and the initial run
CMD ["/entrypoint.sh"]
