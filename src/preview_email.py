#!/usr/bin/env python3

import json
import os
import webbrowser
from datetime import datetime
from email_renderer import EmailRenderer

def preview_email(client_index=0, output_dir='preview'):
    """
    Generate preview files for both HTML and text versions of the email.
    
    Args:
        client_index: Index of the client in clients.json to preview
        output_dir: Directory to save preview files
    """
    # Create output directory if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Load client data
    config_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config')
    with open(os.path.join(config_dir, 'clients.json'), 'r') as f:
        client_data = json.load(f)['clients'][client_index]
    
    # Initialize email renderer
    renderer = EmailRenderer()
    
    # Use a sample maintenance date
    maintenance_date = "Monday, March 3rd, 2025"
    
    # Generate email
    email_message = renderer.render_email(client_data, maintenance_date)
    
    # Save text version
    text_content = email_message.get_payload(0).get_payload()
    text_file = os.path.join(output_dir, 'email_preview.txt')
    with open(text_file, 'w') as f:
        f.write(f"To: {email_message['To']}\n")
        if 'Cc' in email_message:
            f.write(f"Cc: {email_message['Cc']}\n")
        f.write(f"Subject: {email_message['Subject']}\n")
        f.write(f"From: {email_message['From']}\n")
        f.write("\n")
        f.write(text_content)
    
    # Save HTML version with email client-like interface
    html_content = email_message.get_payload(1).get_payload()
    html_file = os.path.join(output_dir, 'email_preview.html')
    
    email_client_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Email Preview - {email_message['Subject']}</title>
        <style>
            body {{
                margin: 0;
                padding: 20px;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                background: #f5f5f5;
            }}
            .email-client {{
                max-width: 800px;
                margin: 0 auto;
                background: white;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                overflow: hidden;
            }}
            .email-header {{
                background: #f8f9fa;
                padding: 20px;
                border-bottom: 1px solid #dee2e6;
            }}
            .header-row {{
                margin: 8px 0;
                display: flex;
            }}
            .header-label {{
                width: 80px;
                color: #6c757d;
                font-weight: 500;
            }}
            .header-content {{
                color: #212529;
                flex: 1;
            }}
            .email-body {{
                padding: 20px;
                background: white;
            }}
            .preview-note {{
                text-align: center;
                padding: 10px;
                background: #e9ecef;
                color: #6c757d;
                font-size: 0.9em;
                margin-bottom: 20px;
            }}
        </style>
    </head>
    <body>
        <div class="preview-note">
            Email Preview - How the email will appear to recipients
        </div>
        <div class="email-client">
            <div class="email-header">
                <div class="header-row">
                    <div class="header-label">From:</div>
                    <div class="header-content">{email_message['From']}</div>
                </div>
                <div class="header-row">
                    <div class="header-label">To:</div>
                    <div class="header-content">{email_message['To']}</div>
                </div>
                {'<div class="header-row"><div class="header-label">Cc:</div><div class="header-content">' + email_message['Cc'] + '</div></div>' if 'Cc' in email_message else ''}
                <div class="header-row">
                    <div class="header-label">Subject:</div>
                    <div class="header-content">{email_message['Subject']}</div>
                </div>
                <div class="header-row">
                    <div class="header-label">Date:</div>
                    <div class="header-content">{email_message['Date']}</div>
                </div>
            </div>
            <div class="email-body">
                {html_content}
            </div>
        </div>
    </body>
    </html>
    """
    
    with open(html_file, 'w') as f:
        f.write(email_client_html)
    
    print(f"\nEmail preview files generated:")
    print(f"1. Text version: {text_file}")
    print(f"2. HTML version: {html_file}")
    
    # Open HTML preview in browser
    webbrowser.open(f"file://{os.path.abspath(html_file)}")

if __name__ == "__main__":
    preview_email()
