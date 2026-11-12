import json
import logging
from typing import Dict, Any, List, Optional
from groq import Groq

import config

logger = logging.getLogger(__name__)

class GroqClientError(Exception):
    pass

class GroqAIClient:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or config.GROQ_API_KEY
        if not self.api_key:
            raise GroqClientError(
                "Groq API key not found. Please set GROQ_API_KEY in your .env file.\n"
                "You can get a free key at https://console.groq.com/keys"
            )
        self.client = Groq(api_key=self.api_key)
        self.model = model or config.GROQ_MODEL
        self.fallback_model = config.GROQ_FALLBACK_MODEL

    def _call_llm(self, messages: List[Dict[str, str]], json_mode: bool = False, temperature: float = 0.3) -> str:
        kwargs: Dict[str, Any] = {
            "messages": messages,
            "temperature": temperature,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                **kwargs
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.warning(f"Primary model {self.model} error: {e}. Trying fallback {self.fallback_model}...")
            try:
                response = self.client.chat.completions.create(
                    model=self.fallback_model,
                    **kwargs
                )
                return response.choices[0].message.content.strip()
            except Exception as fallback_err:
                raise GroqClientError(f"Groq API call failed: {fallback_err}")

    def summarize_email(self, subject: str, sender: str, body: str) -> Dict[str, Any]:
        system_prompt = (
            "You are an expert executive email assistant. Analyze the incoming email and return a valid JSON object "
            "with exactly these keys:\n"
            "- 'summary': (str) Concise 2-3 sentence executive summary of the email\n"
            "- 'key_points': (list of str) 2-4 key takeaways\n"
            "- 'action_required': (bool) True if the recipient needs to respond or do something, False otherwise\n"
            "- 'action_items': (list of str) Specific tasks/actions requested or expected from recipient\n"
            "- 'category': (str) One of ['Work', 'Personal', 'Urgent', 'Finance', 'Newsletter', 'Support', 'Notification', 'Other']\n"
            "- 'priority': (str) One of ['High', 'Medium', 'Low']\n"
            "- 'sentiment': (str) One of ['Positive', 'Neutral', 'Urgent', 'Inquiry', 'Discontent']\n"
            "Respond ONLY with valid JSON."
        )

        user_content = (
            f"Subject: {subject}\n"
            f"From: {sender}\n\n"
            f"Body:\n{body[:4000]}"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]

        raw_output = self._call_llm(messages, json_mode=True, temperature=0.2)
        try:
            return json.loads(raw_output)
        except json.JSONDecodeError:
            return {
                "summary": raw_output,
                "key_points": [],
                "action_required": False,
                "action_items": [],
                "category": "General",
                "priority": "Medium",
                "sentiment": "Neutral"
            }

    def generate_reply(
        self,
        subject: str,
        sender: str,
        body: str,
        tone: str = "professional",
        user_instructions: Optional[str] = None,
        summary: Optional[str] = None
    ) -> str:
        tone_guidelines = {
            "professional": "Clear, polite, formal, and business-appropriate.",
            "concise": "Direct, brief, minimal words while remaining polite.",
            "friendly": "Warm, collegial, helpful, and appreciative.",
            "assertive": "Firm, direct, confident, and unambiguous.",
        }
        chosen_tone_desc = tone_guidelines.get(tone.lower(), f"Tone style: {tone}")

        system_prompt = (
            "You are an AI email assistant drafting a reply on behalf of the user. "
            f"Tone style requested: {chosen_tone_desc}\n\n"
            "Guidelines:\n"
            "- Address the sender appropriately.\n"
            "- Directly address the main questions or requests in the original email.\n"
            "- If custom user instructions are provided, follow them strictly.\n"
            "- Do not invent facts, meetings, or promises not indicated by user instructions.\n"
            "- If information is needed that you don't know, use a placeholder like '[Insert details]'.\n"
            "- Provide ONLY the body of the reply email (with sign-off like 'Best regards, [Your Name]'). Do not include subject lines or headers."
        )

        user_prompt_parts = [
            f"Original Email Subject: {subject}",
            f"From: {sender}",
        ]
        if summary:
            user_prompt_parts.append(f"Email Summary: {summary}")

        user_prompt_parts.append(f"\nOriginal Email Body:\n{body[:3500]}")

        if user_instructions:
            user_prompt_parts.append(f"\nSpecific Instructions for the reply:\n{user_instructions}")

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "\n".join(user_prompt_parts)}
        ]

        return self._call_llm(messages, json_mode=False, temperature=0.5)

    def polish_draft(self, draft: str, tone: str = "professional") -> str:
        if not draft or not draft.strip():
            return ""
        system_prompt = (
            f"You are an executive email communication expert. Polish and refine the user's draft into a "
            f"compelling, clear, and error-free email with a '{tone}' tone. "
            "Preserve all key details, facts, and intent. Provide ONLY the polished email body."
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": draft}
        ]
        return self._call_llm(messages, json_mode=False, temperature=0.3)
