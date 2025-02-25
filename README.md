# Maintenance Scheduler

A Dockerized Python application that automates scheduling maintenance tasks and sends email notifications. It integrates with Google Calendar for scheduling and uses cron jobs to perform regular checks and notifications.

## Table of Contents
1. [Features](#features)
2. [Prerequisites](#prerequisites)
3. [Setup & Installation](#setup--installation)
4. [Configuration Guide](#configuration-guide)
5. [Logging and Data Storage](#logging-and-data-storage)
6. [Running the Application](#running-the-application)
7. [Google Calendar Integration](#google-calendar-integration)
8. [Email Preview & Testing](#email-preview--testing)
9. [Troubleshooting](#troubleshooting)
10. [Contributing & License](#contributing--license)

## Features

### Core Features
- **Smart Scheduling**
  - Automated maintenance window scheduling based on client preferences
  - Conflict detection and avoidance
  - Flexible scheduling windows with customizable parameters
  - Excluded dates support for holidays and blackout periods
  - Timezone support for scheduling

- **Email Notifications**
  - Multiple email sending options:
    - SMTP support with TLS
    - Amazon SES integration
  - Personalized email notifications for each client
  - HTML and plain text email templates
  - CC support for additional stakeholders
  - Duplicate prevention (one notification per maintenance window)
  - Email tracking and archiving
  - Automatic cleanup of old email outputs

- **Google Calendar Integration**
  - Automatic calendar event creation
  - Availability checking across multiple calendars
  - Configurable event visibility
  - Custom reminders for company and clients
  - OAuth2 authentication with auto-refresh
  - Mock calendar mode for testing
  - Support for multiple calendar checking
  - Configurable reminder settings (email and popup)

- **Automation & Monitoring**
  - Cron-based scheduled checks
  - Comprehensive logging system
    - Application logs in `data/maintenance_scheduler.log`
    - Cron execution logs in `data/cron.log`
  - Email preview functionality
  - Automatic old log cleanup
  - Sent notification tracking

### Client Configuration Options
Each client in `clients.json` can be configured with:
```json
{
    "id": "unique_id",
    "client_first_name": "Name",
    "client_email_to": ["primary@email.com"],
    "client_email_cc": ["cc@email.com"],
    "client_website_name": "website.com",
    "maintenance_window": {
        "schedule_range_from": 1,     // Day of month to start looking
        "schedule_range_to": 5,       // Day of month to end looking
        "preferred_days": ["Monday", "Tuesday"],
        "excluded_dates": ["2025-12-25"],
        "preferred_time": "16:30",
        "flexibility_hours": 1,       // Hours +/- preferred time
        "duration_hours": 2          // Length of maintenance window
    },
    "active": true
}
```

### Global Configuration Options
Application settings in `config.json`:
```json
{
    "company": {
        "name": "Company Name",
        "sender_name": "Maintenance Team",
        "sender_email": "maintenance@company.com"
    },
    "email": {
        "subject_template": "Maintenance Scheduled for {maintenance_date}",
        "template_html": "templates/maintenance_email.html",
        "template_text": "templates/maintenance_email.txt"
    },
    "calendar": {
        "check_all_calendars": true,
        "create_events": true,
        "event_visibility": "default",
        "company_reminders": true,
        "client_reminders": false,
        "reminders": {
            "email": 1440,  // Minutes before (24 hours)
            "popup": 60     // Minutes before (1 hour)
        }
    },
    "scheduling": {
        "timezone": "Australia/Sydney",
        "advance_notice_days": 14,
        "minimum_notice_days": 2,
        "allow_multiple_bookings_per_day": false
    }
}
```

## Prerequisites
- Docker ([Installation Guide](https://docs.docker.com/get-docker/))
- Docker Compose ([Installation Guide](https://docs.docker.com/compose/install/))
- Google Cloud account (for Calendar integration)

## Setup & Installation

1. **Clone and Setup**
   ```bash
   git clone <repository_url>
   cd maintenance-scheduler
   cp .env.example .env
   ```

2. **Environment Configuration**
   Edit `.env` with required settings:
   ```ini
   # Email Sender Selection
   EMAIL_SENDER=smtp  # or 'ses' for Amazon SES

   # SMTP Configuration
   SMTP_HOST=smtp.example.com
   SMTP_PORT=465
   SMTP_USERNAME=your_smtp_username
   SMTP_PASSWORD=your_smtp_password
   SMTP_USE_TLS=true

   # AWS SES Configuration (if using SES)
   AWS_ACCESS_KEY_ID=your_access_key
   AWS_SECRET_ACCESS_KEY=your_secret_key
   AWS_REGION=us-east-1

   # Google Calendar Settings
   GOOGLE_CALENDAR_ID=primary  # Use 'primary' or 'all'
   GOOGLE_CLIENT_ID=your-client-id
   GOOGLE_CLIENT_SECRET=your-client-secret
   MOCK_CALENDAR=false

   # Docker Configuration
   USER_ID=1000
   GROUP_ID=1000

   # Timezone
   CRON_TIMEZONE=Australia/Adelaide
   ```

3. **Application Configuration**
   ```bash
   cp config/config.example.json config/config.json
   cp config/clients.example.json config/clients.json
   ```
   Edit both files according to your needs using the configuration options detailed above.

## Configuration Guide

### Logging and Data Storage
The application maintains several important files:
- `data/maintenance_scheduler.log`: Main application logs
- `data/cron.log`: Cron job execution logs
- `data/sent_notifications.json`: Tracks sent notifications
- `data/output/`: Stores copies of sent emails
- `preview/`: Contains email previews for testing

The application includes automatic cleanup utilities for:
- Old email outputs
- Log file size management
- Sent notification history

### Data Retention and Cleanup
The application automatically manages data retention:
- **Email Outputs:** Removed after 30 days
- **Log Entries:** Cleaned up after 30 days
- **Notification History:** Tracked in `data/sent_notifications.json`

To customize retention periods, modify the cleanup utility calls in `main.py`.

### Email Templates
The application uses Jinja2 templates for email generation. Example templates are provided and should be copied and customized for your use:

1. **Copy Example Templates**
   ```bash
   cp templates/maintenance_email.example.html templates/maintenance_email.html
   cp templates/maintenance_email.example.txt templates/maintenance_email.txt
   cp templates/email_signature.example.html templates/email_signature.html
   cp templates/email_signature.example.txt templates/email_signature.txt
   ```

2. **Customize Templates**
   Edit the copied templates with your company's information. Available template variables:
   ```
   client_first_name    : Client's first name
   client_website_name  : Website name
   maintenance_date     : Formatted maintenance date
   maintenance_duration : Duration in hours
   sender_name         : Name from config
   company_name        : Company name from config
   ```

3. **Template Structure**
   - `maintenance_email.html`: Main HTML email template
   - `maintenance_email.txt`: Plain text email template
   - `email_signature.html`: HTML signature (included in HTML template)
   - `email_signature.txt`: Plain text signature (included in text template)

   Note: The example templates are provided for reference and should not be modified directly.
   Instead, copy them and customize your copies.

4. **Email Preview**
   After customizing templates, use the preview feature to verify the layout:
   ```bash
   python src/preview_email.py --client 0
   ```

## Running the Application

1. **Start the Container**
   ```bash
   docker-compose up --build
   ```

2. **View Logs**
   - Application logs: `data/maintenance_scheduler.log`
   - Cron logs: `data/cron.log`
   - Note: The scheduler runs every minute at 9:00 (configurable via crontab)

## Google Calendar Integration

1. **Setup Google Cloud Project**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select existing
   - Enable Google Calendar API
   - Create OAuth 2.0 credentials:
     - Application type: Desktop
     - Download credentials and update `.env`

2. **Calendar Features**
   - Check availability across all calendars or primary only
   - Create events with customizable visibility
   - Set different reminders for company and clients:
     - Email reminders (default: 24 hours before)
     - Popup reminders (default: 1 hour before)
   - Auto-refresh of expired OAuth tokens
   - Mock calendar mode for testing
   - Support for multiple calendar checking
   - Configurable reminder settings (email and popup)

3. **First-time Authorization**
   ```bash
   python src/main.py --preview --client 0
   ```
   - Follow browser prompts to authorize
   - Token will be saved as `.google_token.json`
   - Token auto-refreshes when expired

## Email Preview & Testing

1. **Preview Specific Client Email**
   ```bash
   python src/preview_email.py --client 0
   ```
   This will:
   - Create a `preview` directory if it doesn't exist
   - Generate both HTML and text versions of the email
   - Use a sample maintenance date (March 3rd, 2025)
   - Save preview files as:
     - `preview/email_preview.html`
     - `preview/email_preview.txt`

2. **Test with Mock Calendar**
   ```bash
   MOCK_CALENDAR=true python src/main.py --preview
   ```

3. **Force Specific Date**
   ```bash
   python src/main.py --force-date "Monday, March 3rd, 2025"
   ```

## Troubleshooting

### Permission Issues
- **Docker Volume Permissions**
  ```bash
  # Check ownership of data directory
  ls -l data/
  # Fix permissions if needed
  chown -R $USER_ID:$GROUP_ID data/
  ```
- **Token File Access**
  ```bash
  # Ensure token file is readable
  chmod 600 .google_token.json
  ```

### Cron Issues
- **Check Cron Status**
  ```bash
  # View cron service status
  docker exec scheduler ps aux | grep cron
  # View cron logs
  tail -f data/cron.log
  ```
- **Timezone Issues**
  - Verify `CRON_TIMEZONE` in `.env`
  - Check system timezone matches container

### Email Problems
- **SMTP Connection**
  ```bash
  # Test SMTP connection
  telnet $SMTP_HOST $SMTP_PORT
  ```
- **Email Templates**
  - Verify template paths in `config.json`
  - Check template syntax
  - Preview email before sending

### Calendar Integration
- **Token Issues**
  - Delete `.google_token.json` to reauthorize
  - Check Google Cloud Console credentials
- **Calendar Access**
  - Verify calendar permissions
  - Test with `MOCK_CALENDAR=true`
- **Event Creation**
  - Check calendar write permissions
  - Verify event creation settings in `config.json`

## Contributing & License
- Contributions welcome via pull requests
- Licensed under the Apache License, Version 2.0 - see [LICENSE](./LICENSE) file for details
- Copyright 2025 Pixel Key
