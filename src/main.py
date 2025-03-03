#!/usr/bin/env python3

import json
import logging
import smtplib
import sys
import os
import argparse
import webbrowser
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

from dotenv import load_dotenv
from schedule_handler import ScheduleHandler
from email_renderer import EmailRenderer
from email_sender import EmailSender
from cleanup_utils import cleanup_output_folder, cleanup_log_file


class MaintenanceScheduler:
    def __init__(self, config_path: str = "config/config.json", clients_path: str = "config/clients.json"):
        """Initialize the maintenance scheduler."""
        # Convert paths to absolute paths
        self.project_root = Path(__file__).parent.parent
        config_path = self.project_root / config_path
        clients_path = self.project_root / clients_path
        
        # Load environment variables
        load_dotenv()
        
        # Set up logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.project_root / 'data/maintenance_scheduler.log'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        # Load configuration
        self.config = self._load_json(config_path)
        self.clients = self._load_json(clients_path)['clients']
        
        # Initialize components
        self.schedule_handler = ScheduleHandler(config_path)
        self.email_renderer = EmailRenderer(config_path)
        self.email_sender = EmailSender(self.config)
        self.logger = logging.getLogger(__name__)
        
        # Set up SMTP connection parameters
        self.smtp_config = {
            'host': os.getenv('SMTP_HOST', 'smtp.gmail.com'),
            'port': int(os.getenv('SMTP_PORT', 587)),
            'username': os.getenv('SMTP_USERNAME'),
            'password': os.getenv('SMTP_PASSWORD')
        }
        
        # Create output directory
        self.output_dir = self.project_root / 'data/output'
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _load_json(self, file_path: str) -> Dict[str, Any]:
        """Load and parse a JSON file."""
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            self.logger.error(f"Configuration file not found: {file_path}")
            raise
        except json.JSONDecodeError:
            self.logger.error(f"Invalid JSON in configuration file: {file_path}")
            raise

    def _load_sent_notifications(self) -> Dict:
        """Load the sent notifications tracking file."""
        sent_file = self.project_root / 'data/sent_notifications.json'
        if not sent_file.exists():
            return {"sent_notifications": {}}
        with open(sent_file) as f:
            return json.load(f)

    def _save_sent_notifications(self, data: Dict):
        """Save the sent notifications tracking file."""
        sent_file = self.project_root / 'data/sent_notifications.json'
        sent_file.parent.mkdir(exist_ok=True)
        with open(sent_file, 'w') as f:
            json.dump(data, f, indent=4)

    def has_notification_been_sent(self, client_id: str, maintenance_date: datetime) -> bool:
        """Check if notification was already sent for this maintenance month or current month."""
        sent_data = self._load_sent_notifications()
        client_data = sent_data['sent_notifications'].get(client_id, {})
        
        current_month = datetime.now().strftime("%Y-%m")
        
        # Check if notification was sent this month
        if client_data.get('last_notification_sent', '')[:7] == current_month:
            return True
            
        # Also check if there's already a maintenance scheduled for the current month
        if client_data.get('last_maintenance_date', '')[:7] == current_month:
            return True
            
        return False

    def is_date_available(self, target_date: datetime) -> bool:
        """Check if any other client has maintenance scheduled for the given date."""
        # If multiple bookings per day are allowed, always return True
        if self.config['scheduling'].get('allow_multiple_bookings_per_day', False):
            return True
            
        sent_data = self._load_sent_notifications()
        target_date_str = target_date.strftime("%Y-%m-%d")
        
        # Check all clients' maintenance dates
        for client_id, client_data in sent_data['sent_notifications'].items():
            maintenance_date = client_data.get('last_maintenance_date')
            if maintenance_date and maintenance_date == target_date_str:
                self.logger.info(f"Date {target_date_str} already has maintenance scheduled")
                return False
        return True

    def record_sent_notification(self, client_id: str, maintenance_date: datetime) -> None:
        """Record that a notification was sent."""
        sent_data = self._load_sent_notifications()
        
        if 'sent_notifications' not in sent_data:
            sent_data['sent_notifications'] = {}
        
        sent_data['sent_notifications'][client_id] = {
            'last_notification_sent': datetime.now().strftime("%Y-%m-%d"),
            'last_maintenance_date': maintenance_date.strftime("%Y-%m-%d")
        }
        
        self._save_sent_notifications(sent_data)

    def _save_email_copy(self, email_message, client_data: Dict[str, Any], maintenance_date: str) -> str:
        """Save a copy of the sent email in a timestamped directory."""
        # Create timestamp-based directory
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        client_name = client_data['client_first_name'].lower().replace(' ', '_')
        website_name = client_data['client_website_name'].lower().replace('.', '_')
        
        # Create directory structure: output/YYYYMMDD_HHMMSS_clientname_websitename/
        email_dir = self.output_dir / f"{timestamp}_{client_name}_{website_name}"
        email_dir.mkdir(exist_ok=True)
        
        # Save metadata
        metadata = {
            'timestamp': timestamp,
            'client_name': client_data['client_first_name'],
            'website_name': client_data['client_website_name'],
            'maintenance_date': maintenance_date,
            'to_email': email_message['To'],
            'cc_email': email_message.get('Cc', ''),
            'subject': email_message['Subject']
        }
        
        with open(email_dir / 'metadata.json', 'w') as f:
            json.dump(metadata, f, indent=2)
        
        # Save text version
        text_content = email_message.get_payload(0).get_payload()
        with open(email_dir / 'email.txt', 'w') as f:
            f.write(f"To: {email_message['To']}\n")
            if 'Cc' in email_message:
                f.write(f"Cc: {email_message['Cc']}\n")
            f.write(f"Subject: {email_message['Subject']}\n")
            f.write(f"From: {email_message['From']}\n")
            f.write("\n")
            f.write(text_content)
        
        # Save HTML version
        html_content = email_message.get_payload(1).get_payload()
        with open(email_dir / 'email.html', 'w') as f:
            f.write(f"<!-- To: {email_message['To']} -->\n")
            if 'Cc' in email_message:
                f.write(f"<!-- Cc: {email_message['Cc']} -->\n")
            f.write(f"<!-- Subject: {email_message['Subject']} -->\n")
            f.write(f"<!-- From: {email_message['From']} -->\n")
            f.write("\n")
            f.write(html_content)
        
        return str(email_dir)

    def process_client(self, client_data: Dict[str, Any], preview_mode: bool = False, force_date: Optional[str] = None) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Process a single client's maintenance scheduling."""
        try:
            client_id = client_data['id']  # This is the correct ID from clients.json
            client_name = client_data['client_first_name']
            website = client_data['client_website_name']
            
            # Check if notification already sent for current month before any calendar operations
            if not force_date and self.has_notification_been_sent(client_id, datetime.now()):
                return True, None
            
            # Find next maintenance window
            window = self.schedule_handler.get_next_maintenance_window(client_data)
            if not window:
                self.logger.warning(f"No suitable maintenance window found for {website}")
                return False, None

            start_time, end_time = window
            
            # Check if the date is available (no other maintenance scheduled)
            if not self.is_date_available(start_time):
                self.logger.warning(f"Date {start_time.strftime('%Y-%m-%d')} already has maintenance scheduled, trying next window")
                return False, None
            
            maintenance_date = self.schedule_handler.format_maintenance_date(start_time)

            # In preview mode, just generate the email
            if preview_mode:
                email_message = self.email_renderer.render_email(client_data, maintenance_date)
                return True, {
                    'message': email_message,
                    'maintenance_date': maintenance_date,
                    'client': client_data
                }

            # Check if it's time to send notification based on advance_notice_days
            today = datetime.now(self.schedule_handler.timezone)
            days_until_maintenance = (start_time.date() - today.date()).days
            
            if days_until_maintenance > self.config['scheduling']['advance_notice_days']:
                return True, None
            
            # Try to create calendar event first
            try:
                event_id = self.schedule_handler.create_maintenance_event(client_data, start_time, end_time)
            except ValueError as e:
                if "Time slot is no longer available" in str(e):
                    self.logger.warning(f"Selected time slot is no longer available, retrying with a new slot")
                    # Recursively try again with a new time slot
                    return self.process_client(client_data, preview_mode, force_date)
                raise
            except Exception as e:
                self.logger.error(f"Failed to create calendar event: {str(e)}")
                # Continue even if calendar event creation fails
            
            # Generate and send email
            email_message = self.email_renderer.render_email(client_data, maintenance_date)
            self._send_email(email_message)
            
            # Record the sent notification
            self.record_sent_notification(client_id, start_time)
            
            # Save email copy
            output_path = self._save_email_copy(email_message, client_data, maintenance_date)
            self.logger.info(f"Email copy saved to: {output_path}")
            
            self.logger.info(f"Email sent successfully to {client_data['client_email_to']}, {', '.join(client_data['client_email_cc'])}")
            return True, None
            
        except Exception as e:
            self.logger.error(f"Error processing client {client_data.get('id', 'Unknown')}: {str(e)}")
            return False, None

    def _send_email(self, email_message):
        """Send an email using configured email sender."""
        try:
            # Get recipients
            to_emails = [email_message['To']]
            cc_emails = [email_message['Cc']] if 'Cc' in email_message else None
            
            # Send the email
            if self.email_sender.send_email(email_message, to_emails, cc_emails):
                return True
            else:
                self.logger.error("Failed to send email")
                return False
                
        except Exception as e:
            self.logger.error(f"Error sending email: {str(e)}")
            return False

    def preview_email(self, client_index: int = 0, output_dir: str = 'data/preview', force_date: Optional[str] = None) -> bool:
        """Generate preview files for both HTML and text versions of the email."""
        try:
            if not (0 <= client_index < len(self.clients)):
                self.logger.error(f"Invalid client index: {client_index}")
                return False

            client_data = self.clients[client_index]
            if not client_data.get('active', True):
                self.logger.warning(f"Client {client_data.get('id', 'unknown')} is not active")
                return False

            # Create preview directory
            preview_dir = self.project_root / output_dir
            preview_dir.mkdir(parents=True, exist_ok=True)

            success, result = self.process_client(client_data, preview_mode=True, force_date=force_date)
            
            if not success or not result:
                self.logger.error("Failed to generate email preview")
                return False

            email_message = result['message']
            
            # Save text version
            text_content = email_message.get_payload(0).get_payload()
            text_file = preview_dir / 'email_preview.txt'
            with open(text_file, 'w') as f:
                f.write(f"To: {email_message['To']}\n")
                if 'Cc' in email_message:
                    f.write(f"Cc: {email_message['Cc']}\n")
                f.write(f"Subject: {email_message['Subject']}\n")
                f.write(f"From: {email_message['From']}\n")
                f.write("\n")
                f.write(text_content)
            
            # Save HTML version
            html_content = email_message.get_payload(1).get_payload()
            html_file = preview_dir / 'email_preview.html'
            with open(html_file, 'w') as f:
                f.write(f"<!-- To: {email_message['To']} -->\n")
                if 'Cc' in email_message:
                    f.write(f"<!-- Cc: {email_message['Cc']} -->\n")
                f.write(f"<!-- Subject: {email_message['Subject']} -->\n")
                f.write(f"<!-- From: {email_message['From']} -->\n")
                f.write("\n")
                f.write(html_content)
            
            self.logger.info(f"\nEmail preview files generated:")
            self.logger.info(f"1. Text version: {text_file}")
            self.logger.info(f"2. HTML version: {html_file}")
            
            # Open HTML preview in default browser
            webbrowser.open(f'file://{os.path.abspath(html_file)}')
            return True
        
        except Exception as e:
            self.logger.error(f"Failed to generate email preview: {str(e)}")
            return False

    def cleanup_old_data(self):
        """Clean up old output files and log entries."""
        output_dir = os.path.join(self.project_root, 'data', 'output')
        log_file = os.path.join(self.project_root, 'data', 'maintenance_scheduler.log')
        cron_log_file = os.path.join(self.project_root, 'data', 'cron.log')
        
        # Get retention days from config or use defaults
        logs_config = self.config.get('logs_cleanup', {})
        output_retention_days = logs_config.get('output_files_retention_days', 90)
        maintenance_log_retention_days = logs_config.get('maintenance_log_retention_days', 90)
        cron_log_retention_days = logs_config.get('cron_log_retention_days', 90)
        
        self.logger.info(f"Cleaning up files older than: output={output_retention_days} days, "
                         f"maintenance log={maintenance_log_retention_days} days, "
                         f"cron log={cron_log_retention_days} days")
        
        cleanup_output_folder(output_dir, self.logger, days=output_retention_days)
        cleanup_log_file(log_file, self.logger, days=maintenance_log_retention_days)
        cleanup_log_file(cron_log_file, self.logger, days=cron_log_retention_days)

    def run(self, preview_mode: bool = False, client_index: Optional[int] = None, force_date: Optional[str] = None) -> None:
        """Run the maintenance scheduling process."""
        self.logger.info("Starting maintenance scheduling process")
        
        if force_date:
            os.environ['FORCE_MAINTENANCE_DATE'] = force_date
        
        # Filter active clients
        active_clients = [c for c in self.clients if c.get('active', True)]
        
        # Process specific client if index provided
        if client_index is not None:
            if 0 <= client_index < len(active_clients):
                clients_to_process = [active_clients[client_index]]
            else:
                self.logger.error(f"Invalid client index: {client_index}")
                return
        else:
            clients_to_process = active_clients
        
        processed_count = 0
        for client in clients_to_process:
            try:
                success, _ = self.process_client(client, preview_mode, force_date)
                if success:
                    processed_count += 1
            except Exception as e:
                self.logger.error(f"Error processing client {client.get('client_first_name', 'Unknown')}: {str(e)}")
        
        self.logger.info(
            f"Completed maintenance scheduling. "
            f"Processed {processed_count}/{len(clients_to_process)} active clients successfully."
        )
        
        # Clean up old data after successful run
        self.cleanup_old_data()


def main():
    parser = argparse.ArgumentParser(description='Maintenance Email Scheduler')
    parser.add_argument('--preview', action='store_true',
                      help='Generate email preview without sending')
    parser.add_argument('--client', type=int, default=None,
                      help='Process specific client by index')
    parser.add_argument('--force-date', type=str,
                      help='Force a specific maintenance date (e.g., "Monday, March 3rd, 2025")')
    parser.add_argument('--config', type=str, default='config/config.json',
                      help='Path to config file')
    parser.add_argument('--clients', type=str, default='config/clients.json',
                      help='Path to clients file')

    args = parser.parse_args()

    try:
        scheduler = MaintenanceScheduler(args.config, args.clients)
        scheduler.run(
            preview_mode=args.preview,
            client_index=args.client,
            force_date=args.force_date
        )
    except Exception as e:
        logging.error(f"Fatal error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
