import json
import os
from typing import Dict, Any
from jinja2 import Environment, FileSystemLoader
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


class EmailRenderer:
    def __init__(self, config_path: str = "config/config.json"):
        """Initialize the email renderer with configuration."""
        # Convert config_path to absolute path
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), config_path)
        self.config = self._load_json(config_path)
        self.template_env = Environment(
            loader=FileSystemLoader(os.path.dirname(self.config["email"]["template_html"]))
        )
        self.html_template = self.template_env.get_template(
            os.path.basename(self.config["email"]["template_html"])
        )
        self.text_template = self.template_env.get_template(
            os.path.basename(self.config["email"]["template_text"])
        )

    def _load_json(self, file_path: str) -> Dict[str, Any]:
        """Load and parse a JSON file."""
        with open(file_path, 'r') as f:
            return json.load(f)

    def render_email(self, client_data: Dict[str, Any], maintenance_date: str) -> MIMEMultipart:
        """
        Render both HTML and text versions of the email for a client.
        
        Args:
            client_data: Dictionary containing client information
            maintenance_date: Formatted date string for the maintenance window
            
        Returns:
            MIMEMultipart: Email message with both HTML and text versions
        """
        # Prepare template variables
        template_vars = {
            'client_first_name': client_data['client_first_name'],
            'client_website_name': client_data['client_website_name'],
            'maintenance_date': maintenance_date,
            'maintenance_duration': client_data['maintenance_window']['duration_hours'],
            'sender_name': self.config['company']['sender_name'],
            'company_name': self.config['company']['name']
        }

        # Create the email message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = self.config['email']['subject_template'].format(
            website_name=client_data['client_website_name'],
            maintenance_date=maintenance_date
        )
        msg['From'] = self.config['company']['sender_email']
        
        # Handle To field (ensure it's a list)
        to_emails = client_data['client_email_to']
        if not isinstance(to_emails, list):
            to_emails = [to_emails]
        msg['To'] = ', '.join(to_emails)
        
        # Handle Cc field
        if client_data.get('client_email_cc'):
            cc_emails = client_data['client_email_cc']
            if not isinstance(cc_emails, list):
                cc_emails = [cc_emails]
            msg['Cc'] = ', '.join(cc_emails)

        # Render and attach both text and HTML versions
        text_part = MIMEText(
            self.text_template.render(**template_vars),
            'plain'
        )
        html_part = MIMEText(
            self.html_template.render(**template_vars),
            'html'
        )

        # Attach parts into message container
        # According to RFC 2046, the last part of a multipart message is preferred
        msg.attach(text_part)
        msg.attach(html_part)

        return msg

    def get_email_recipients(self, client_data: Dict[str, Any]) -> list:
        """Get all email recipients (To and Cc) for a client."""
        # Handle To field (can be string or list)
        to_emails = client_data['client_email_to']
        recipients = [to_emails] if isinstance(to_emails, str) else to_emails.copy()
        
        # Add CC recipients if any
        if client_data.get('client_email_cc'):
            recipients.extend(client_data['client_email_cc'])
        return recipients


if __name__ == '__main__':
    # Example usage
    renderer = EmailRenderer()
    
    # Load sample client data
    with open('clients.json', 'r') as f:
        client_data = json.load(f)['clients'][0]  # Get first client
    
    # Example maintenance date
    maintenance_date = "Monday, March 3rd, 2025"
    
    # Render email
    email_message = renderer.render_email(client_data, maintenance_date)
    
    # Print the email content for testing
    print("Subject:", email_message['Subject'])
    print("From:", email_message['From'])
    print("To:", email_message['To'])
    if email_message['Cc']:
        print("Cc:", email_message['Cc'])
    print("\nText version:")
    print(email_message.get_payload(0).get_payload())
    print("\nHTML version:")
    print(email_message.get_payload(1).get_payload())
