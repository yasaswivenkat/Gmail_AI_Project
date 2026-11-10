import os
import sys
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build, Resource

import config

class GmailAuthError(Exception):
    """Raised when authentication fails or credentials are missing."""
    pass

def check_credentials_file() -> tuple[bool, str]:
    if not config.CREDENTIALS_FILE.exists():
        return False, (
            f"Google Cloud credentials file not found at: {config.CREDENTIALS_FILE}\n\n"
            "Please provide your 'credentials.json' (OAuth 2.0 Client ID credentials from Google Cloud Console).\n"
            "Steps to obtain it:\n"
            "1. Visit https://console.cloud.google.com/\n"
            "2. Create a project and enable the 'Gmail API'.\n"
            "3. Go to 'APIs & Services' > 'OAuth consent screen', select 'External' or 'Internal' and configure app info.\n"
            "4. Go to 'APIs & Services' > 'Credentials' > 'Create Credentials' > 'OAuth client ID'.\n"
            "5. Select Application Type: 'Desktop app'.\n"
            "6. Download the JSON file, rename it to 'credentials.json', and place it in the project root folder."
        )
    return True, "Credentials file found."

def is_authorized() -> bool:
    if not config.TOKEN_FILE.exists():
        return False
    try:
        creds = Credentials.from_authorized_user_file(str(config.TOKEN_FILE), config.GMAIL_SCOPES)
        return creds and (creds.valid or (creds.expired and creds.refresh_token))
    except Exception:
        return False

def get_gmail_service() -> Resource:
    creds = None
    
    if config.TOKEN_FILE.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(config.TOKEN_FILE), config.GMAIL_SCOPES)
        except Exception:
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None

        if not creds:
            ok, msg = check_credentials_file()
            if not ok:
                raise GmailAuthError(msg)

            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(config.CREDENTIALS_FILE),
                    config.GMAIL_SCOPES
                )
                print("\n[OAuth] Starting local authentication server...", flush=True)
                print("[OAuth] A browser window will open automatically for Google Sign-In.", flush=True)
                creds = flow.run_local_server(port=0, prompt="consent")
            except Exception as e:
                raise GmailAuthError(f"Failed to complete OAuth authentication: {e}")

        try:
            with open(config.TOKEN_FILE, "w", encoding="utf-8") as token_file:
                token_file.write(creds.to_json())
            print(f"[OAuth] Successfully saved credentials to {config.TOKEN_FILE.name}", flush=True)
        except Exception as e:
            print(f"Warning: Could not save {config.TOKEN_FILE}: {e}", file=sys.stderr)

    return build("gmail", "v1", credentials=creds)

if __name__ == "__main__":
    print("Testing Gmail Authentication...")
    svc = get_gmail_service()
    profile = svc.users().getProfile(userId="me").execute()
    print(f"Authentication successful! Connected account: {profile.get('emailAddress')}")
