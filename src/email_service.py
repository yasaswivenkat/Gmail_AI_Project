import logging
from typing import List, Dict, Any, Optional

from src.gmail_client import GmailClient
from src.groq_client import GroqAIClient
import config

logger = logging.getLogger(__name__)

class EmailAutomationService:
    def __init__(
        self,
        gmail_client: Optional[GmailClient] = None,
        groq_client: Optional[GroqAIClient] = None
    ):
        self._gmail_client = gmail_client
        self._groq_client = groq_client

    @property
    def gmail(self) -> GmailClient:
        if self._gmail_client is None:
            self._gmail_client = GmailClient()
        return self._gmail_client

    @property
    def groq(self) -> GroqAIClient:
        if self._groq_client is None:
            self._groq_client = GroqAIClient()
        return self._groq_client

    def fetch_and_analyze_inbox(
        self,
        query: str = "is:unread",
        limit: int = 10,
        summarize: bool = True
    ) -> List[Dict[str, Any]]:
        emails = self.gmail.fetch_inbox_emails(query=query, max_results=limit)
        analyzed_emails = []

        for email in emails:
            result = dict(email)
            if summarize:
                try:
                    analysis = self.groq.summarize_email(
                        subject=email["subject"],
                        sender=email["sender"],
                        body=email["body"]
                    )
                    result["analysis"] = analysis
                except Exception as e:
                    logger.error(f"Failed to summarize email {email['id']}: {e}")
                    result["analysis"] = {
                        "summary": email.get("snippet", ""),
                        "key_points": [],
                        "action_required": False,
                        "action_items": [],
                        "category": "Unknown",
                        "priority": "Medium",
                        "sentiment": "Neutral",
                    }
            analyzed_emails.append(result)

        return analyzed_emails

    def analyze_single_email(self, email_id: str) -> Dict[str, Any]:
        email = self.gmail.get_message(email_id)
        analysis = self.groq.summarize_email(
            subject=email["subject"],
            sender=email["sender"],
            body=email["body"]
        )
        email["analysis"] = analysis
        return email

    def generate_email_reply(
        self,
        email_id: str,
        tone: str = "professional",
        custom_instructions: Optional[str] = None
    ) -> Dict[str, Any]:
        email = self.gmail.get_message(email_id)
        
        subject = email["subject"]
        if not subject.lower().startswith("re:"):
            reply_subject = f"Re: {subject}"
        else:
            reply_subject = subject

        recipient = email["sender"]
        reply_body = self.groq.generate_reply(
            subject=email["subject"],
            sender=email["sender"],
            body=email["body"],
            tone=tone,
            user_instructions=custom_instructions
        )

        return {
            "email_id": email_id,
            "thread_id": email["thread_id"],
            "to": recipient,
            "subject": reply_subject,
            "reply_body": reply_body,
            "in_reply_to": email.get("message_id_header"),
            "references": email.get("references") or email.get("message_id_header"),
        }

    def send_reply(
        self,
        email_id: str,
        reply_body: str,
        mark_as_read: bool = True
    ) -> Dict[str, Any]:
        email = self.gmail.get_message(email_id)
        subject = email["subject"]
        reply_subject = subject if subject.lower().startswith("re:") else f"Re: {subject}"

        sent = self.gmail.send_email(
            to=email["sender"],
            subject=reply_subject,
            body=reply_body,
            thread_id=email["thread_id"],
            in_reply_to=email.get("message_id_header"),
            references=email.get("references") or email.get("message_id_header"),
        )

        if mark_as_read:
            self.gmail.mark_as_read(email_id)

        return sent

    def save_reply_draft(
        self,
        email_id: str,
        reply_body: str
    ) -> Dict[str, Any]:
        email = self.gmail.get_message(email_id)
        subject = email["subject"]
        reply_subject = subject if subject.lower().startswith("re:") else f"Re: {subject}"

        return self.gmail.create_draft(
            to=email["sender"],
            subject=reply_subject,
            body=reply_body,
            thread_id=email["thread_id"],
            in_reply_to=email.get("message_id_header"),
            references=email.get("references") or email.get("message_id_header"),
        )

    def send_new_email(self, to: str, subject: str, body: str) -> Dict[str, Any]:
        return self.gmail.send_email(to=to, subject=subject, body=body)

    def process_batch(
        self,
        query: str = "is:unread",
        limit: int = 5,
        auto_send: bool = False,
        tone: str = "professional"
    ) -> List[Dict[str, Any]]:
        emails = self.fetch_and_analyze_inbox(query=query, limit=limit, summarize=True)
        results = []

        for item in emails:
            analysis = item.get("analysis", {})
            action_req = analysis.get("action_required", False)

            status = {
                "id": item["id"],
                "subject": item["subject"],
                "from": item["sender"],
                "category": analysis.get("category", "General"),
                "priority": analysis.get("priority", "Medium"),
                "action_required": action_req,
                "summary": analysis.get("summary", ""),
                "action_taken": "None"
            }

            if action_req:
                try:
                    reply_info = self.generate_email_reply(item["id"], tone=tone)
                    reply_text = reply_info["reply_body"]
                    status["generated_reply"] = reply_text

                    if auto_send:
                        self.send_reply(item["id"], reply_text, mark_as_read=True)
                        status["action_taken"] = "Reply Sent & Marked Read"
                    else:
                        draft = self.save_reply_draft(item["id"], reply_text)
                        status["action_taken"] = f"Draft Created in Gmail (Draft ID: {draft.get('id', '')})"
                except Exception as e:
                    status["action_taken"] = f"Failed to process reply: {e}"
            else:
                status["action_taken"] = "No reply needed"

            results.append(status)

        return results

    def polish_email_draft(self, text: str, tone: str = "professional") -> str:
        return self.groq.polish_draft(text, tone=tone)
