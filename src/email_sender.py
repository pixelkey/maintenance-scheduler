import os
import smtplib
import boto3
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Any
import logging
from botocore.exceptions import ClientError

class EmailSender:
    def __init__(self, config: Dict[str, Any]):
        """Initialize the email sender with configuration."""
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.sender_type = os.getenv('EMAIL_SENDER', 'smtp').lower()  # 'smtp' or 'ses'
        
        # SES client (only initialize if using SES)
        self.ses_client = None
        if self.sender_type == 'ses':
            self.ses_client = boto3.client(
                'ses',
                aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
                region_name=os.getenv('AWS_REGION', 'us-east-1')
            )
    
    def send_email(self, email_message: MIMEMultipart, to_emails: List[str], cc_emails: List[str] = None) -> bool:
        """Send an email using either SMTP or SES based on configuration."""
        try:
            if self.sender_type == 'ses':
                return self._send_via_ses(email_message, to_emails, cc_emails)
            else:
                return self._send_via_smtp(email_message, to_emails, cc_emails)
        except Exception as e:
            self.logger.error(f"Failed to send email: {str(e)}")
            return False

    def _send_via_smtp(self, email_message: MIMEMultipart, to_emails: List[str], cc_emails: List[str] = None) -> bool:
        """Send email using SMTP."""
        try:
            # The email headers are already set by the email renderer
            # Connect to SMTP server
            with smtplib.SMTP(self.config['email']['smtp_host'], self.config['email']['smtp_port']) as server:
                if self.config['email'].get('smtp_use_tls', True):
                    server.starttls()
                
                # Login if credentials are provided
                if self.config['email'].get('smtp_username'):
                    server.login(
                        self.config['email']['smtp_username'],
                        self.config['email']['smtp_password']
                    )
                
                # Send email
                recipients = to_emails + (cc_emails if cc_emails else [])
                server.send_message(email_message, to_addrs=recipients)
                
                self.logger.info(f"Email sent successfully to {', '.join(to_emails)}" + 
                               (f", {', '.join(cc_emails)}" if cc_emails else ""))
                return True

        except Exception as e:
            self.logger.error(f"SMTP send failed: {str(e)}")
            return False

    def _send_via_ses(self, email_message: MIMEMultipart, to_emails: List[str], cc_emails: List[str] = None) -> bool:
        """Send email using Amazon SES."""
        try:
            # Send the email via SES (headers are already set by email renderer)
            response = self.ses_client.send_raw_email(
                Source=email_message['From'],
                Destinations=to_emails + (cc_emails if cc_emails else []),
                RawMessage={
                    'Data': email_message.as_string()
                }
            )
            
            message_id = response['MessageId']
            self.logger.info(f"Email sent successfully via SES (ID: {message_id}) to {', '.join(to_emails)}" +
                           (f", {', '.join(cc_emails)}" if cc_emails else ""))
            return True

        except ClientError as e:
            self.logger.error(f"SES send failed: {str(e)}")
            return False
