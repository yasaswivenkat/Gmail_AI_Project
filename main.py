import os
import sys
import argparse
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm

import config
from src.auth import check_credentials_file, GmailAuthError
from src.email_service import EmailAutomationService
from src.groq_client import GroqClientError

console = Console()

def print_banner():
    """Print welcoming CLI banner."""
    console.print(
        Panel.fit(
            "[bold cyan]AI-Powered Email Automation System[/bold cyan]\n"
            "[green]Powered by Gmail API & Groq LLM[/green]\n"
            f"[dim]Groq Model: {config.GROQ_MODEL} | Workspace: {config.BASE_DIR.name}[/dim]",
            border_style="cyan"
        )
    )

def check_system_status(show_details: bool = True) -> bool:
    """Validate credentials and API configuration."""
    all_ok = True
    console.print("\n[bold]Checking System Status & Credentials:[/bold]")

    creds_ok, creds_msg = check_credentials_file()
    if creds_ok:
        console.print("  [bold green][OK][/bold green] Google Cloud credentials file: [cyan]credentials.json found[/cyan]")
    else:
        console.print("  [bold red][X][/bold red] Google Cloud credentials file: [yellow]credentials.json missing[/yellow]")
        if show_details:
            console.print(Panel(creds_msg, title="[yellow]Action Required: Google Cloud Console JSON[/yellow]", border_style="yellow"))
        all_ok = False

    if config.TOKEN_FILE.exists():
        console.print(f"  [bold green][OK][/bold green] Gmail OAuth Token: [cyan]{config.TOKEN_FILE.name} found (authorized)[/cyan]")
    else:
        console.print(f"  [bold yellow][*][/bold yellow] Gmail OAuth Token: [dim]{config.TOKEN_FILE.name} not found (will be created upon first login)[/dim]")

    if config.GROQ_API_KEY and not config.GROQ_API_KEY.startswith("gsk_your"):
        masked_key = config.GROQ_API_KEY[:6] + "..." + config.GROQ_API_KEY[-4:]
        console.print(f"  [bold green][OK][/bold green] Groq API Key: [cyan]Configured ({masked_key})[/cyan]")
    else:
        console.print("  [bold red][X][/bold red] Groq API Key: [yellow]Missing or placeholder in .env[/yellow]")
        console.print("    [dim]Set GROQ_API_KEY in your .env file (get one free at https://console.groq.com/keys)[/dim]")
        all_ok = False

    console.print()
    return all_ok

def action_summarize_inbox(service: EmailAutomationService, limit: int = 5, query: str = "is:unread"):
    """Fetch and summarize inbox emails."""
    with console.status(f"[bold cyan]Fetching and summarizing {limit} emails with Groq...[/bold cyan]", spinner="dots"):
        try:
            emails = service.fetch_and_analyze_inbox(query=query, limit=limit, summarize=True)
        except GmailAuthError as e:
            console.print(f"[bold red]Gmail Auth Error:[/bold red] {e}")
            return
        except GroqClientError as e:
            console.print(f"[bold red]Groq Error:[/bold red] {e}")
            return
        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] {e}")
            return

    if not emails:
        console.print(f"[yellow]No messages found matching query: '{query}'[/yellow]")
        return

    table = Table(title=f"Inbox Emails ({query})", show_header=True, header_style="bold magenta", expand=True)
    table.add_column("#", style="dim", width=4)
    table.add_column("From", style="cyan", width=25)
    table.add_column("Subject", style="white", width=30)
    table.add_column("Priority", justify="center", width=10)
    table.add_column("Category", width=12)
    table.add_column("AI Summary", style="green")

    for idx, em in enumerate(emails, 1):
        analysis = em.get("analysis", {})
        priority = analysis.get("priority", "Medium")
        p_color = "red" if priority == "High" else "yellow" if priority == "Medium" else "blue"
        
        table.add_row(
            str(idx),
            em.get("sender", "")[:24],
            em.get("subject", "")[:28],
            f"[{p_color}]{priority}[/{p_color}]",
            analysis.get("category", "General"),
            analysis.get("summary", em.get("snippet", ""))
        )

    console.print(table)
    return emails

def action_inspect_and_reply(service: EmailAutomationService):
    """Inspect a specific email and generate an AI draft reply."""
    emails = action_summarize_inbox(service, limit=5, query="is:unread")
    if not emails:
        return

    choice = Prompt.ask("\nEnter email number to inspect & generate reply (or press Enter to skip)", default="")
    if not choice or not choice.isdigit():
        return

    idx = int(choice) - 1
    if idx < 0 or idx >= len(emails):
        console.print("[red]Invalid email number.[/red]")
        return

    selected = emails[idx]
    analysis = selected.get("analysis", {})

    console.print(Panel(
        f"[bold]From:[/bold] {selected.get('sender')}\n"
        f"[bold]Subject:[/bold] {selected.get('subject')}\n"
        f"[bold]Date:[/bold] {selected.get('date')}\n"
        f"[bold]Category:[/bold] {analysis.get('category')} | [bold]Priority:[/bold] {analysis.get('priority')}\n\n"
        f"[bold cyan]AI Summary:[/bold cyan]\n{analysis.get('summary')}\n\n"
        f"[bold cyan]Key Action Items:[/bold cyan]\n" + 
        ("\n".join(f"• {item}" for item in analysis.get('action_items', [])) or "None identified") + "\n\n"
        f"[bold]Body Preview:[/bold]\n{selected.get('body')[:600]}...",
        title="[bold yellow]Email Details[/bold yellow]",
        border_style="yellow"
    ))

    if not Confirm.ask("Would you like to generate an AI reply for this email?", default=True):
        return

    tone = Prompt.ask(
        "Select tone",
        choices=["professional", "concise", "friendly", "assertive"],
        default="professional"
    )

    custom_notes = Prompt.ask("Any specific instructions or points to include? (Optional)", default="")

    with console.status("[bold cyan]Generating AI reply with Groq...[/bold cyan]", spinner="dots"):
        reply_info = service.generate_email_reply(
            email_id=selected["id"],
            tone=tone,
            custom_instructions=custom_notes if custom_notes else None
        )

    reply_body = reply_info["reply_body"]

    console.print(Panel(
        f"[bold]To:[/bold] {reply_info['to']}\n"
        f"[bold]Subject:[/bold] {reply_info['subject']}\n\n"
        f"{reply_body}",
        title="[bold green]Generated AI Reply[/bold green]",
        border_style="green"
    ))

    action = Prompt.ask(
        "Action to take",
        choices=["Send Now", "Save to Gmail Drafts", "Cancel"],
        default="Save to Gmail Drafts"
    )

    if action == "Send Now":
        with console.status("[cyan]Sending email reply via Gmail...[/cyan]"):
            service.send_reply(selected["id"], reply_body, mark_as_read=True)
        console.print("[bold green]Reply successfully sent and original marked as read![/bold green]")
    elif action == "Save to Gmail Drafts":
        with console.status("[cyan]Creating draft in Gmail...[/cyan]"):
            draft = service.save_reply_draft(selected["id"], reply_body)
        console.print(f"[bold green]Draft saved successfully in Gmail! (Draft ID: {draft.get('id')})[/bold green]")
    else:
        console.print("[yellow]Reply discarded.[/yellow]")

def action_send_new(service: EmailAutomationService):
    """Compose and send a new email."""
    console.print("\n[bold]Compose New Email[/bold]")
    to = Prompt.ask("To (recipient email address)")
    subject = Prompt.ask("Subject")
    body = Prompt.ask("Body / Message")

    if not to or not subject:
        console.print("[red]Recipient and Subject are required.[/red]")
        return

    if Confirm.ask(f"Send email to {to}?", default=True):
        with console.status("[cyan]Sending email via Gmail API...[/cyan]"):
            service.send_new_email(to=to, subject=subject, body=body)
        console.print("[bold green]Email sent successfully![/bold green]")

def action_batch_workflow(service: EmailAutomationService):
    """Run batch auto-reply workflow on unread emails."""
    limit = int(Prompt.ask("How many unread emails to process?", default="5"))
    auto_send = Confirm.ask(
        "Auto-send replies directly? (Select 'No' to safely create Gmail Drafts for review)",
        default=False
    )
    tone = Prompt.ask("Default reply tone", choices=["professional", "concise", "friendly"], default="professional")

    with console.status(f"[cyan]Running batch workflow on {limit} emails...[/cyan]"):
        results = service.process_batch(limit=limit, auto_send=auto_send, tone=tone)

    table = Table(title="Batch Processing Results", show_header=True, header_style="bold cyan")
    table.add_column("Subject", style="white")
    table.add_column("Category", style="cyan")
    table.add_column("Priority", style="yellow")
    table.add_column("Action Taken", style="green")

    for res in results:
        table.add_row(res["subject"][:35], res["category"], res["priority"], res["action_taken"])

    console.print(table)

def interactive_loop():
    """Main interactive terminal loop."""
    print_banner()
    check_system_status(show_details=False)

    service = EmailAutomationService()

    while True:
        console.print("\n[bold cyan]Select an Option:[/bold cyan]")
        console.print("  [1] Read & Summarize Inbox (Unread)")
        console.print("  [2] Inspect Email & Generate AI Reply")
        console.print("  [3] Send New Outgoing Email")
        console.print("  [4] Run Batch Auto-Reply / Draft Workflow")
        console.print("  [5] Validate System Setup & Google Credentials")
        console.print("  [0] Exit")

        choice = Prompt.ask("\nEnter choice", choices=["0", "1", "2", "3", "4", "5"], default="1")

        if choice == "0":
            console.print("[dim]Goodbye![/dim]")
            break
        elif choice == "1":
            action_summarize_inbox(service, limit=5)
        elif choice == "2":
            action_inspect_and_reply(service)
        elif choice == "3":
            action_send_new(service)
        elif choice == "4":
            action_batch_workflow(service)
        elif choice == "5":
            check_system_status(show_details=True)

def action_authenticate():
    """Run initial OAuth authentication and print status."""
    from src.auth import get_gmail_service
    try:
        with console.status("[cyan]Authenticating with Google OAuth...[/cyan]"):
            svc = get_gmail_service()
            profile = svc.users().getProfile(userId="me").execute()
        console.print(f"[bold green]Successfully authenticated![/bold green] Connected to: [cyan]{profile.get('emailAddress')}[/cyan]")
    except Exception as e:
        console.print(f"[bold red]Authentication failed:[/bold red] {e}")

def main():
    parser = argparse.ArgumentParser(description="AI-Powered Email Automation System")
    parser.add_argument("--action", choices=["status", "auth", "summarize", "auto-reply", "send"], help="Direct action to execute")
    parser.add_argument("--limit", type=int, default=5, help="Number of emails to fetch")
    parser.add_argument("--query", type=str, default="is:unread", help="Gmail query filter")
    parser.add_argument("--auto-send", action="store_true", help="Automatically send replies instead of saving drafts")
    parser.add_argument("--to", type=str, help="Recipient email address for --action send")
    parser.add_argument("--subject", type=str, help="Subject for --action send")
    parser.add_argument("--body", type=str, help="Body text for --action send")

    args = parser.parse_args()

    if not args.action:
        interactive_loop()
        return

    if args.action == "auth":
        action_authenticate()
        return

    service = EmailAutomationService()

    if args.action == "status":
        check_system_status(show_details=True)
    elif args.action == "summarize":
        action_summarize_inbox(service, limit=args.limit, query=args.query)
    elif args.action == "auto-reply":
        results = service.process_batch(query=args.query, limit=args.limit, auto_send=args.auto_send)
        for r in results:
            console.print(f"- [bold]{r['subject']}[/bold]: {r['action_taken']}")
    elif args.action == "send":
        if not args.to or not args.subject or not args.body:
            console.print("[red]Error: --to, --subject, and --body are required for --action send[/red]")
            sys.exit(1)
        service.send_new_email(to=args.to, subject=args.subject, body=args.body)
        console.print("[green]Email sent successfully.[/green]")

if __name__ == "__main__":
    main()

