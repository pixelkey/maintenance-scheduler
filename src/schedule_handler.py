from __future__ import print_function

import os
from os import path
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import logging
from dotenv import load_dotenv

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import pytz
from dateutil.parser import parse
from dateutil.relativedelta import relativedelta, MO, TU, WE, TH, FR


class ScheduleHandler:
    # If modifying these scopes, delete the file token.json.
    SCOPES = [
        'https://www.googleapis.com/auth/calendar.readonly',
        'https://www.googleapis.com/auth/calendar.events'
    ]
    
    # Map day names to dateutil constants
    DAY_MAP = {
        'Monday': MO,
        'Tuesday': TU,
        'Wednesday': WE,
        'Thursday': TH,
        'Friday': FR
    }

    def __init__(self, config_path: str = "config/config.json"):
        """Initialize the schedule handler with configuration."""
        # Convert config_path to absolute path
        config_path = os.path.abspath(config_path)
        self.config = self._load_json(config_path)
        self.timezone = pytz.timezone(self.config['scheduling']['timezone'])
        self.logger = logging.getLogger(__name__)
        
        # Load environment from .env file
        load_dotenv(override=True)
        
        # Load Google Calendar settings from environment
        self.client_id = os.getenv('GOOGLE_CLIENT_ID')
        self.client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
        self.calendar_id = os.getenv('GOOGLE_CALENDAR_ID', 'primary')
        
        # Set token path in config directory
        self.token_path = os.path.join(os.path.dirname(config_path), 'token.json')
        
        # Initialize calendar service
        self.service = self._get_calendar_service()

    def _load_json(self, file_path: str) -> Dict[str, Any]:
        """Load and parse a JSON file."""
        with open(file_path, 'r') as f:
            return json.load(f)

    def _get_calendar_service(self):
        """Get or create Google Calendar service."""
        # For testing without Google Calendar
        mock_calendar = os.getenv('MOCK_CALENDAR', 'true').lower() == 'true'
        self.logger.info(f"MOCK_CALENDAR is set to: {os.getenv('MOCK_CALENDAR', 'true')}")
        
        if mock_calendar:
            self.logger.info("Using mock calendar service for testing")
            return None
            
        self.logger.info("Using real Google Calendar service")
        creds = None
        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(self.token_path, self.SCOPES)
            
        # If credentials don't exist or are invalid, get new ones
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                # Create flow with explicit application name
                flow = InstalledAppFlow.from_client_config(
                    {
                        "installed": {
                            "client_id": self.client_id,
                            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                            "token_uri": "https://oauth2.googleapis.com/token",
                            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                            "client_secret": self.client_secret,
                            "redirect_uris": ["http://localhost"]
                        }
                    },
                    self.SCOPES
                )
                
                creds = flow.run_local_server(
                    port=0,
                    success_message="Authorization successful! You may close this window."
                )
                
                # Save the credentials for the next run
                os.makedirs(os.path.dirname(self.token_path), exist_ok=True)
                with open(self.token_path, 'w') as token:
                    token.write(creds.to_json())

        return build('calendar', 'v3', credentials=creds)

    def get_next_maintenance_window(self, client_data: Dict[str, Any]) -> Optional[Tuple[datetime, datetime]]:
        """
        Find the next available maintenance window for a client.
        
        Args:
            client_data: Dictionary containing client scheduling preferences
            
        Returns:
            Tuple of (start_time, end_time) or None if no suitable window found
        """
        # For testing without Google Calendar, just return the forced date if provided
        mock_calendar = os.getenv('MOCK_CALENDAR', 'true').lower() == 'true'
        if mock_calendar:
            from_date = datetime.now(self.timezone)
            min_notice_days = self.config['scheduling'].get('minimum_notice_days', 1)
            advance_notice_days = self.config['scheduling']['advance_notice_days']
            
            # Calculate earliest allowed date based on minimum notice
            earliest_date = from_date + timedelta(days=min_notice_days)
            maintenance_date = from_date + timedelta(days=advance_notice_days)
            
            # Ensure maintenance_date is not before earliest_date
            if maintenance_date < earliest_date:
                maintenance_date = earliest_date
            
            # If a specific date was forced, use that but respect minimum notice
            forced_date = os.getenv('FORCE_MAINTENANCE_DATE')
            if forced_date:
                try:
                    maintenance_date = parse(forced_date)
                    if not maintenance_date.tzinfo:
                        maintenance_date = self.timezone.localize(maintenance_date)
                    # Ensure forced date respects minimum notice
                    if maintenance_date < earliest_date:
                        self.logger.warning(f"Forced date {maintenance_date} is before minimum notice period. Using {earliest_date} instead.")
                        maintenance_date = earliest_date
                except ValueError as e:
                    self.logger.error(f"Error parsing forced date: {e}")
            
            # Get maintenance duration from client config
            duration_hours = client_data['maintenance_window'].get('duration_hours', 2)  # default 2 hours for backward compatibility
            start_time = maintenance_date.replace(hour=10, minute=0)  # Default to 10 AM
            end_time = start_time + timedelta(hours=duration_hours)
            return start_time, end_time
        
        try:
            maintenance_window = client_data['maintenance_window']
            range_from = maintenance_window['schedule_range_from']
            range_to = maintenance_window['schedule_range_to']
            preferred_days = maintenance_window.get('preferred_days', ['Monday', 'Tuesday', 'Wednesday', 'Thursday'])
            excluded_dates = [parse(date) for date in maintenance_window.get('excluded_dates', [])]
            
            # Get current date and calculate dates
            today = datetime.now(self.timezone)
            self.logger.info(f"Finding maintenance window for {client_data['client_first_name']}")
            self.logger.info(f"Today's date: {today}")
            self.logger.info(f"Preferred days: {preferred_days}")

            # Get minimum notice period
            min_notice_days = self.config['scheduling'].get('minimum_notice_days', 1)
            earliest_date = today + timedelta(days=min_notice_days)
            
            # Generate potential dates
            potential_dates = []
            advance_notice_days = self.config['scheduling']['advance_notice_days']
            
            # Calculate the date range to check
            start_date = earliest_date  # Use earliest_date instead of today
            end_date = today + timedelta(days=advance_notice_days)
            
            # Convert range_from/to to actual dates in the current/next month
            current_month = today.month
            current_year = today.year
            next_month = current_month + 1 if current_month < 12 else 1
            next_year = current_year if current_month < 12 else current_year + 1
            
            # Create dates for the range in both current and next month
            range_dates = []
            for day in range(range_from, range_to + 1):
                # Try current month
                try:
                    date = today.replace(day=day)
                    if date >= start_date:
                        range_dates.append(date)
                except ValueError:
                    pass  # Skip invalid dates (e.g., Feb 31)
                
                # Try next month
                try:
                    date = today.replace(year=next_year, month=next_month, day=day)
                    if date <= end_date:
                        range_dates.append(date)
                except ValueError:
                    pass  # Skip invalid dates
            
            self.logger.info(f"Checking dates from {start_date.strftime('%B %d')} to {end_date.strftime('%B %d')}")
            
            # Filter dates by weekday and excluded dates
            for date in range_dates:
                # Only include weekdays that are in preferred_days
                day_name = date.strftime('%A')
                if day_name in preferred_days and date not in excluded_dates:
                    potential_dates.append(date)
                    self.logger.info(f"Added potential date: {date.strftime('%A, %B %d')}")
            
            if not potential_dates:
                self.logger.warning(f"No potential dates found in range {range_from}-{range_to}")
                return None

            # Sort dates by preferred days and chronologically
            weekday_map = {'Monday': 0, 'Tuesday': 1, 'Wednesday': 2, 'Thursday': 3, 'Friday': 4}
            preferred_weekdays = [weekday_map[day] for day in preferred_days]
            self.logger.info(f"Preferred weekdays (0=Mon, 4=Fri): {preferred_weekdays}")
            
            potential_dates.sort(key=lambda d: (
                d.weekday() not in preferred_weekdays,
                d
            ))
            
            self.logger.info("Sorted potential dates:")
            for date in potential_dates:
                self.logger.info(f"- {date.strftime('%A, %B %d')} (weekday {date.weekday()})")
            
            # Check calendar availability for each potential date
            # Get maintenance duration from client config
            duration_hours = client_data['maintenance_window'].get('duration_hours', 2)  # default 2 hours for backward compatibility
            duration = timedelta(hours=duration_hours)
            
            for date in potential_dates:
                # Get maintenance time preferences
                maintenance_window = client_data.get('maintenance_window', {})
                preferred_time = maintenance_window.get('preferred_time', '16:30')
                flexibility_hours = maintenance_window.get('flexibility_hours', 1)
                
                try:
                    base_hour, base_minute = map(int, preferred_time.split(':'))
                except (ValueError, AttributeError):
                    # If there's any error parsing the time, use default
                    base_hour, base_minute = 16, 30
                
                # Try time slots from preferred time, then try slots before and after
                time_slots = []
                # Add preferred time first
                time_slots.append((base_hour, base_minute))
                
                # Add slots before and after in alternating order
                for offset in range(1, int(flexibility_hours) + 1):
                    # Try one hour before
                    before_hour = base_hour - offset
                    if 0 <= before_hour <= 23:
                        time_slots.append((before_hour, base_minute))
                    
                    # Try one hour after
                    after_hour = base_hour + offset
                    if 0 <= after_hour <= 23:
                        time_slots.append((after_hour, base_minute))
                
                # Try each time slot
                for hour, minute in time_slots:
                    start_time = date.replace(
                        hour=hour,
                        minute=minute,
                        second=0,
                        microsecond=0
                    )
                    end_time = start_time + duration
                    
                    self.logger.info(f"Checking availability for {date.strftime('%A, %B %d')} at {start_time.strftime('%H:%M')}")
                    # Check calendar availability
                    if self._is_time_available(start_time, end_time):
                        self.logger.info(f"Found available slot on {date.strftime('%A, %B %d')} at {start_time.strftime('%H:%M')}")
                        return start_time, end_time
                    else:
                        self.logger.info(f"Slot not available on {date.strftime('%A, %B %d')} at {start_time.strftime('%H:%M')}")

            self.logger.warning("No available slots found in any potential dates")
            return None

        except HttpError as error:
            print(f'An error occurred: {error}')
            return None

    def _is_time_available(self, start_time: datetime, end_time: datetime) -> bool:
        """Check if a time window is available in the calendar."""
        try:
            # Check all calendars if configured to do so
            calendar_ids = []
            if self.config['calendar'].get('check_all_calendars', False):
                calendar_list = self.service.calendarList().list().execute()
                calendar_ids = [calendar['id'] for calendar in calendar_list.get('items', [])]
            else:
                calendar_ids = [self.calendar_id]

            # Check each calendar for events
            for calendar_id in calendar_ids:
                events_result = self.service.events().list(
                    calendarId=calendar_id,
                    timeMin=start_time.isoformat(),
                    timeMax=end_time.isoformat(),
                    maxResults=10,
                    singleEvents=True,
                    orderBy='startTime'
                ).execute()
                
                events = events_result.get('items', [])
                
                # If there are any events during this time in any calendar, the window is not available
                if len(events) > 0:
                    return False

            # If we get here, no events were found in any calendar
            return True

        except HttpError as error:
            print(f'An error occurred: {error}')
            return False

    def format_maintenance_date(self, maintenance_datetime: datetime) -> str:
        """Format the maintenance date for email templates."""
        return maintenance_datetime.strftime("%A, %B %d, %Y")

    def create_maintenance_event(self, client_data: Dict[str, Any], start_time: datetime, end_time: datetime) -> str:
        """Create a maintenance event in Google Calendar.
        
        Args:
            client_data: Client information
            start_time: Start time of maintenance
            end_time: End time of maintenance
            
        Returns:
            str: The created event ID
            
        Raises:
            ValueError: If the time slot is no longer available
        """
        try:
            # Double-check availability right before creating
            if not self._is_time_available(start_time, end_time):
                self.logger.error("Time slot is no longer available (possible race condition)")
                raise ValueError("Time slot is no longer available")

            # Get company email and reminder settings
            company_email = self.config['company']['sender_email']
            company_reminders = self.config['calendar'].get('company_reminders', True)
            client_reminders = self.config['calendar'].get('client_reminders', False)
            reminder_settings = self.config['calendar']['reminders']

            # Create base event details
            event = {
                'summary': f"Website Maintenance - {client_data['client_website_name']}",
                'location': client_data['client_website_name'],
                'description': (
                    f"Scheduled maintenance for {client_data['client_website_name']}\n"
                    f"Client: {client_data['client_first_name']} {client_data.get('client_last_name', '')}\n"
                    f"Contact: {client_data['client_email_to']}"
                ),
                'start': {
                    'dateTime': start_time.isoformat(),
                    'timeZone': self.timezone.zone,
                },
                'end': {
                    'dateTime': end_time.isoformat(),
                    'timeZone': self.timezone.zone,
                }
            }

            # Build attendees list - start with company email
            attendees = [{
                'email': company_email,
                'responseStatus': 'accepted',
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'email', 'minutes': reminder_settings['email']},
                        {'method': 'popup', 'minutes': reminder_settings['popup']}
                    ]
                } if company_reminders else {}
            }]

            # Only add client emails if client_reminders is true
            if client_reminders:
                # Add client email
                attendees.append({
                    'email': client_data['client_email_to'],
                    'responseStatus': 'needsAction'
                })
                
                # Add CC'd emails
                for cc in client_data.get('client_email_cc', []):
                    attendees.append({
                        'email': cc,
                        'responseStatus': 'needsAction'
                    })

            event['attendees'] = attendees
            event['reminders'] = {'useDefault': False}  # Disable default reminders

            # Create the event in the primary calendar or specified calendar ID
            calendar_id = os.getenv('GOOGLE_CALENDAR_ID', 'primary')
            event = self.service.events().insert(
                calendarId=calendar_id,
                body=event,
                sendUpdates='none'  # Don't send any email notifications - we handle that separately
            ).execute()

            self.logger.info(f"Created calendar event: {event.get('htmlLink')}")
            return event['id']

        except Exception as e:
            self.logger.error(f"Failed to create calendar event: {str(e)}")
            raise


if __name__ == '__main__':
    # Example usage
    scheduler = ScheduleHandler()
    
    # Load sample client data
    with open('clients.json', 'r') as f:
        client_data = json.load(f)['clients'][0]  # Get first client
    
    # Find next maintenance window
    window = scheduler.get_next_maintenance_window(client_data)
    
    if window:
        start_time, end_time = window
        print(f"Next maintenance window found:")
        print(f"Date: {scheduler.format_maintenance_date(start_time)}")
        print(f"Time: {start_time.strftime('%I:%M %p')} - {end_time.strftime('%I:%M %p')}")
        
        # Create a maintenance event
        event_id = scheduler.create_maintenance_event(client_data, start_time, end_time)
        print(f"Created maintenance event: {event_id}")
    else:
        print("No suitable maintenance window found")
