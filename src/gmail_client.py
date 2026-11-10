import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Any, Optional

from src.auth import get_gmail_service
from src.utils import extract_email_body

class GmailClient:
    def __init__(self, service=None):
        self.service = service or get_gmail_service()

    def get_user_profile(self) -> Dict[str, Any]:
        return self.service.users().getProfile(userId="me").execute()

    def list_messages(self, query: str = "is:unread", max_results: int = 10) -> List[Dict[str, Any]]:
        response = self.service.users().messages().list(
            userId="me",
            q=query,
            maxResults=max_results
        ).execute()
        return response.get("messages", [])

    def get_message(self, message_id: str) -> Dict[str, Any]:
        raw_msg = self.service.users().messages().get(
            userId="me",
            id=message_id,
            format="full"
        ).execute()

        payload = raw_msg.get("payload", {})
        headers_list = payload.get("headers", [])
        
        headers = {}
        for h in headers_list:
            headers[h["name"].lower()] = h["value"]

        subject = headers.get("subject", "(No Subject)")
        sender = headers.get("from", "Unknown Sender")
        to = headers.get("to", "")
        date = headers.get("date", "")
        message_id_header = headers.get("message-id", "")
        references = headers.get("references", "")

        plain_body, html_body = extract_email_body(payload)

        return {
            "id": raw_msg.get("id"),
            "thread_id": raw_msg.get("threadId"),
            "label_ids": raw_msg.get("labelIds", []),
            "snippet": raw_msg.get("snippet", ""),
            "subject": subject,
            "sender": sender,
            "to": to,
            "date": date,
            "message_id_header": message_id_header,
            "references": references,
            "body": plain_body or raw_msg.get("snippet", ""),
            "html_body": html_body,
        }

    def fetch_inbox_emails(self, query: str = "is:unread", max_results: int = 10) -> List[Dict[str, Any]]:
        summaries = self.list_messages(query=query, max_results=max_results)
        detailed_emails = []
        for item in summaries:
            try:
                email_data = self.get_message(item["id"])
                detailed_emails.append(email_data)
            except Exception as e:
                print(f"Error fetching email {item['id']}: {e}")
        return detailed_emails

    def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        thread_id: Optional[str] = None,
        in_reply_to: Optional[str] = None,
        references: Optional[str] = None,
    ) -> Dict[str, Any]:
        message = MIMEText(body, "plain", "utf-8")
        message["to"] = to
        message["subject"] = subject

        if in_reply_to:
            message["In-Reply-To"] = in_reply_to
        if references:
            message["References"] = references

        raw_payload = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
        send_body: Dict[str, Any] = {"raw": raw_payload}
        if thread_id:
            send_body["threadId"] = thread_id

        return self.service.users().messages().send(
            userId="me",
            body=send_body
        ).execute()

    def create_draft(
        self,
        to: str,
        subject: str,
        body: str,
        thread_id: Optional[str] = None,
        in_reply_to: Optional[str] = None,
        references: Optional[str] = None,
    ) -> Dict[str, Any]:
        message = MIMEText(body, "plain", "utf-8")
        message["to"] = to
        message["subject"] = subject

        if in_reply_to:
            message["In-Reply-To"] = in_reply_to
        if references:
            message["References"] = references

        raw_payload = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
        draft_body: Dict[str, Any] = {"message": {"raw": raw_payload}}
        if thread_id:
            draft_body["message"]["threadId"] = thread_id

        return self.service.users().drafts().create(
            userId="me",
            body=draft_body
        ).execute()

    def mark_as_read(self, message_id: str) -> Dict[str, Any]:
        return self.service.users().messages().modify(
            userId="me",
            id=message_id,
            body={"removeLabelIds": ["UNREAD"]}
        ).execute()

    def add_labels(self, message_id: str, label_ids: List[str]) -> Dict[str, Any]:
        return self.service.users().messages().modify(
            userId="me",
            id=message_id,
            body={"addLabelIds": label_ids}
        ).execute()
