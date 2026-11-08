import base64
import re
from typing import Optional, Dict, Any
from bs4 import BeautifulSoup

def decode_base64_payload(data: str) -> str:
    if not data:
        return ""
    try:
        missing_padding = len(data) % 4
        if missing_padding:
            data += "=" * (4 - missing_padding)
        decoded_bytes = base64.urlsafe_b64decode(data)
        return decoded_bytes.decode("utf-8", errors="replace")
    except Exception:
        return ""

def clean_html_to_text(html_content: str) -> str:
    if not html_content:
        return ""
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        for element in soup(["script", "style", "head", "title", "meta", "[document]"]):
            element.extract()
            
        for br in soup.find_all(["br", "p", "div", "tr"]):
            br.append("\n")
            
        text = soup.get_text()
        lines = [line.strip() for line in text.splitlines()]
        return "\n".join(chunk for chunk in lines if chunk)
    except Exception:
        clean = re.sub(r"<[^>]+>", " ", html_content)
        return re.sub(r"\s+", " ", clean).strip()

def extract_email_body(payload: Dict[str, Any]) -> tuple[str, str]:
    plain_text = ""
    html_text = ""

    def walk_parts(part: Dict[str, Any]):
        nonlocal plain_text, html_text
        mime_type = part.get("mimeType", "")
        body_data = part.get("body", {}).get("data", "")

        if mime_type == "text/plain" and body_data and not plain_text:
            plain_text = decode_base64_payload(body_data)
        elif mime_type == "text/html" and body_data and not html_text:
            html_text = decode_base64_payload(body_data)

        subparts = part.get("parts", [])
        for sub in subparts:
            walk_parts(sub)

    walk_parts(payload)

    if not plain_text and html_text:
        plain_text = clean_html_to_text(html_text)

    return plain_text.strip(), html_text.strip()

def truncate_text(text: str, max_length: int = 300) -> str:
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[:max_length].rstrip() + "..."
