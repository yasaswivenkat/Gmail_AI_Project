import streamlit as st
import time
from datetime import datetime
from typing import Dict, Any, List

import config
from src.auth import check_credentials_file, get_gmail_service, is_authorized, GmailAuthError
from src.email_service import EmailAutomationService
from src.groq_client import GroqAIClient, GroqClientError

st.set_page_config(
    page_title="AI Gmail Copilot",
    page_icon=":material/mail:",
    layout="wide",
    initial_sidebar_state="expanded"
)

creds_ok, creds_msg = check_credentials_file()
auth_ok = is_authorized()
groq_ok = bool(config.GROQ_API_KEY and not config.GROQ_API_KEY.startswith("gsk_your"))

with st.sidebar:
    st.markdown("### :material/mark_email_read: AI Gmail Copilot")
    st.caption("Next-Generation Autonomous Email Intelligence")
    st.divider()

    with st.container(border=True):
        st.markdown("**:material/health_and_safety: System Status**")
        if creds_ok:
            st.markdown(":material/check_circle: :green[Credentials JSON Ready]")
        else:
            st.markdown(":material/cancel: :red[Missing `credentials.json`]")

        if auth_ok:
            st.markdown(":material/verified_user: :green[Gmail OAuth Connected]")
        else:
            st.markdown(":material/warning: :orange[Gmail Authorization Pending]")

        if groq_ok:
            st.markdown(f":material/bolt: :green[Groq AI Active]")
        else:
            st.markdown(":material/cancel: :red[Missing Groq API Key]")

    st.divider()

    st.markdown("**:material/tune: Copilot Settings**")
    active_model = st.selectbox(
        "Groq Model",
        ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"],
        index=0,
        help="Select the LLM powering summarization and smart replies."
    )

    fetch_limit = st.slider(
        "Max Emails to Fetch",
        min_value=3,
        max_value=20,
        value=8,
        step=1
    )

    query_filter = st.selectbox(
        "Folder / Filter",
        ["is:unread", "in:inbox", "is:starred", "label:important", "in:sent"],
        index=0
    )

    st.divider()
    if auth_ok:
        if st.button(":material/logout: Re-authenticate Account", width="stretch"):
            if config.TOKEN_FILE.exists():
                config.TOKEN_FILE.unlink(missing_ok=True)
            st.session_state.clear()
            st.rerun()

service = None
user_email = "Not Connected"
if creds_ok and groq_ok and auth_ok:
    try:
        service = EmailAutomationService(groq_client=GroqAIClient(model=active_model))
        try:
            profile = service.gmail.get_user_profile()
            user_email = profile.get("emailAddress", "Connected")
        except Exception:
            user_email = "Connected"
    except Exception as e:
        st.error(f"Error initializing services: {e}", icon=":material/error:")

h_col1, h_col2 = st.columns([3, 1], vertical_alignment="center")
with h_col1:
    st.title("AI-Powered Email Studio")
    st.caption("Autonomous reading, smart executive summaries, and intelligent context-aware replies")
with h_col2:
    if auth_ok:
        st.markdown(
            f"<div style='text-align: right;'>"
            f"<span style='background:#EEF2FF; color:#4F46E5; padding:6px 14px; border-radius:20px; font-weight:600; font-size:13px;'>"
            f"Account: {user_email}</span></div>",
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            "<div style='text-align: right;'>"
            "<span style='background:#FEF3C7; color:#B45309; padding:6px 14px; border-radius:20px; font-weight:600; font-size:13px;'>"
            "Sign-in Required</span></div>",
            unsafe_allow_html=True
        )

if not creds_ok:
    with st.container(border=True):
        st.subheader(":material/key: Google Cloud Credentials Required")
        st.markdown(creds_msg)
    st.stop()

if not auth_ok:
    with st.container(border=True):
        st.subheader(":material/lock: Connect Your Gmail Account")
        st.write("Authorize this application with your Gmail account to start reading and replying to emails.")
        col_auth1, col_auth2 = st.columns([1, 2])
        with col_auth1:
            if st.button(":material/login: Authorize in Browser", type="primary", width="stretch"):
                with st.spinner("Opening Google OAuth Sign-In in your browser..."):
                    try:
                        get_gmail_service()
                        st.toast("Authorization Successful!", icon=":material/check_circle:")
                        st.rerun()
                    except Exception as e:
                        st.error(f"OAuth failed: {e}", icon=":material/error:")
        with col_auth2:
            st.info("Or run in terminal: `.venv\\Scripts\\python.exe main.py --action auth`", icon=":material/terminal:")
    st.stop()

tab_inbox, tab_compose, tab_batch, tab_analytics = st.tabs([
    ":material/inbox: Smart Inbox",
    ":material/edit_note: Compose & Polish",
    ":material/bolt: Autonomous Batching",
    ":material/insights: Analytics & Insights"
])

with tab_inbox:
    top_c1, top_c2, top_c3, top_c4 = st.columns([1.5, 1, 1, 1], vertical_alignment="bottom")
    with top_c1:
        search_kw = st.text_input(
            "Search Emails",
            placeholder="Search by sender, subject, keyword...",
            label_visibility="collapsed"
        )
    with top_c2:
        filter_mode = st.segmented_control(
            "Filter",
            options=["All", "Action Required", "High Priority"],
            default="All",
            label_visibility="collapsed"
        )
    with top_c3:
        if st.button(":material/refresh: Refresh Mailbox", width="stretch"):
            st.session_state.pop("cached_emails", None)
            st.session_state.pop("selected_email_id", None)
            st.rerun()
    with top_c4:
        st.caption(f"Folder: `{query_filter}` | Limit: `{fetch_limit}`")

    if "cached_emails" not in st.session_state:
        with st.spinner("Analyzing inbox emails with Groq..."):
            try:
                emails_raw = service.fetch_and_analyze_inbox(
                    query=query_filter,
                    limit=fetch_limit,
                    summarize=True
                )
                st.session_state["cached_emails"] = emails_raw
            except Exception as e:
                st.error(f"Failed to fetch emails: {e}", icon=":material/error:")
                st.session_state["cached_emails"] = []

    emails = st.session_state.get("cached_emails", [])

    filtered_emails = []
    for em in emails:
        analysis = em.get("analysis", {})
        if search_kw:
            kw = search_kw.lower()
            text_pool = f"{em.get('subject', '')} {em.get('sender', '')} {analysis.get('summary', '')}".lower()
            if kw not in text_pool:
                continue
        if filter_mode == "Action Required" and not analysis.get("action_required", False):
            continue
        if filter_mode == "High Priority" and analysis.get("priority", "").lower() != "high":
            continue
        filtered_emails.append(em)

    unread_count = len([e for e in emails if "UNREAD" in e.get("label_ids", [])])
    action_count = len([e for e in emails if e.get("analysis", {}).get("action_required")])
    high_count = len([e for e in emails if e.get("analysis", {}).get("priority") == "High"])

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    with kpi1:
        st.metric("Total Fetched", len(emails), border=True)
    with kpi2:
        st.metric("Unread Messages", unread_count, border=True)
    with kpi3:
        st.metric("Action Required", action_count, border=True)
    with kpi4:
        st.metric("High Priority", high_count, border=True)

    st.write("")

    if not filtered_emails:
        st.info("No emails match your current filter or search criteria.", icon=":material/search_off:")
    else:
        col_list, col_viewer = st.columns([1.1, 1.9], gap="medium")

        if "selected_email_id" not in st.session_state or not any(e["id"] == st.session_state["selected_email_id"] for e in filtered_emails):
            st.session_state["selected_email_id"] = filtered_emails[0]["id"]

        with col_list:
            st.markdown("#### :material/list: Email Feed")
            for em in filtered_emails:
                analysis = em.get("analysis", {})
                priority = analysis.get("priority", "Medium")
                is_selected = (em["id"] == st.session_state["selected_email_id"])

                p_icon = f"[{priority}]"
                action_badge = "Action Needed" if analysis.get("action_required") else ""

                with st.container(border=True):
                    c_title, c_act = st.columns([3, 1])
                    with c_title:
                        st.markdown(f"**{em.get('sender', 'Unknown')[:28]}**")
                        st.markdown(f"*{em.get('subject', '(No Subject)')[:35]}*")
                    with c_act:
                        if st.button("Open", key=f"sel_{em['id']}", type="primary" if is_selected else "secondary", width="stretch"):
                            st.session_state["selected_email_id"] = em["id"]
                            st.rerun()

                    b1, b2, b3 = st.columns([1, 1, 1.2])
                    with b1:
                        st.caption(f"Priority: {priority}")
                    with b2:
                        st.caption(f"Category: {analysis.get('category', 'General')}")
                    with b3:
                        if action_badge:
                            st.caption(f":red[{action_badge}]")

        selected_em = next((e for e in filtered_emails if e["id"] == st.session_state["selected_email_id"]), filtered_emails[0])
        sel_analysis = selected_em.get("analysis", {})

        with col_viewer:
            with st.container(border=True):
                hdr1, hdr2 = st.columns([3, 1])
                with hdr1:
                    st.markdown(f"### {selected_em.get('subject')}")
                    st.markdown(f"**From:** `{selected_em.get('sender')}`")
                    st.caption(f"Date: {selected_em.get('date')} | ID: `{selected_em.get('id')}`")
                with hdr2:
                    if st.button(":material/mark_email_read: Mark Read", key=f"mr_{selected_em['id']}", width="stretch"):
                        service.gmail.mark_as_read(selected_em['id'])
                        st.toast("Marked as read!", icon=":material/check:")

                st.divider()

                st.markdown("#### :material/smart_toy: AI Intelligence Breakdown")
                
                with st.container(border=True):
                    st.markdown("**:material/summarize: Executive Summary:**")
                    st.markdown(f"> *{sel_analysis.get('summary', selected_em.get('snippet'))}*")

                ai_col1, ai_col2 = st.columns(2)
                with ai_col1:
                    with st.container(border=True):
                        st.markdown("**:material/checklist: Key Action Items:**")
                        actions = sel_analysis.get("action_items", [])
                        if actions:
                            for idx_a, act in enumerate(actions):
                                st.checkbox(act, key=f"chk_{selected_em['id']}_{idx_a}")
                        else:
                            st.markdown("*(No action items identified)*")
                with ai_col2:
                    with st.container(border=True):
                        st.markdown("**:material/analytics: Message Tone & Category:**")
                        st.markdown(f"- **Category:** `{sel_analysis.get('category', 'General')}`")
                        st.markdown(f"- **Priority:** `{sel_analysis.get('priority', 'Medium')}`")
                        st.markdown(f"- **Detected Sentiment:** `{sel_analysis.get('sentiment', 'Neutral')}`")

                with st.expander(":material/article: View Original Email Body", expanded=False):
                    st.text_area("Full Body", value=selected_em.get("body", ""), height=220, disabled=True, label_visibility="collapsed")

                st.divider()

                st.markdown("#### :material/reply: Smart AI Reply Studio")

                col_tone, col_preset = st.columns([1.5, 2.5])
                with col_tone:
                    tone_sel = st.segmented_control(
                        "Tone",
                        options=["Professional", "Concise", "Friendly", "Assertive"],
                        default="Professional"
                    )
                with col_preset:
                    preset_instruction = st.pills(
                        "Quick Presets",
                        options=["Acknowledge & Thank", "Confirm & Accept", "Decline Politely", "Request More Details"],
                        default=None
                    )

                custom_guidance = st.text_input(
                    "Custom Reply Instructions (Optional)",
                    placeholder="e.g. Tell them I will look at the report on Monday morning...",
                    value=preset_instruction or ""
                )

                if st.button(":material/auto_awesome: Generate AI Reply Draft", type="primary", width="stretch"):
                    with st.spinner("Drafting contextual reply with Groq..."):
                        reply_data = service.generate_email_reply(
                            email_id=selected_em["id"],
                            tone=(tone_sel or "Professional").lower(),
                            custom_instructions=custom_guidance if custom_guidance else None
                        )
                        st.session_state[f"active_reply_{selected_em['id']}"] = reply_data["reply_body"]
                        st.toast("AI draft generated!", icon=":material/sparkles:")

                current_draft = st.session_state.get(f"active_reply_{selected_em['id']}", "")
                if current_draft:
                    edited_draft = st.text_area(
                        "Review / Refine Your Reply:",
                        value=current_draft,
                        height=180,
                        key=f"text_edit_{selected_em['id']}"
                    )

                    btn_c1, btn_c2, btn_c3 = st.columns([1, 1, 1])
                    with btn_c1:
                        if st.button(":material/send: Send Reply Now", type="primary", width="stretch"):
                            with st.spinner("Sending reply via Gmail..."):
                                service.send_reply(selected_em["id"], edited_draft, mark_as_read=True)
                            st.toast("Reply successfully sent in-thread!", icon=":material/check_circle:")
                            time.sleep(1)
                            st.rerun()
                    with btn_c2:
                        if st.button(":material/drafts: Save to Gmail Drafts", width="stretch"):
                            with st.spinner("Saving draft..."):
                                res_draft = service.save_reply_draft(selected_em["id"], edited_draft)
                            st.toast(f"Saved in Gmail Drafts (ID: {res_draft.get('id')})", icon=":material/bookmark:")
                    with btn_c3:
                        if st.button(":material/delete: Discard Draft", width="stretch"):
                            st.session_state.pop(f"active_reply_{selected_em['id']}", None)
                            st.rerun()

with tab_compose:
    st.markdown("### :material/edit: Compose New Email")
    st.caption("Draft new messages from scratch or let Groq AI polish your rough notes into executive prose.")

    with st.container(border=True):
        col_to, col_sub = st.columns([1, 1])
        with col_to:
            comp_to = st.text_input("Recipient (To)", placeholder="recipient@example.com")
        with col_sub:
            comp_subject = st.text_input("Subject", placeholder="Project Update & Next Steps")

        col_opt1, col_opt2 = st.columns([1, 2])
        with col_opt1:
            polish_tone = st.segmented_control(
                "Tone for Polish",
                ["Professional", "Concise", "Friendly", "Formal"],
                default="Professional"
            )

        compose_text = st.text_area(
            "Email Body or Rough Notes:",
            height=200,
            placeholder="Type your message, or enter rough bullet points to polish with AI...",
            key="compose_body_text"
        )

        act_col1, act_col2 = st.columns([1, 1])
        with act_col1:
            if st.button(":material/auto_fix: Polish & Enhance Draft with AI", width="stretch"):
                if not compose_text.strip():
                    st.warning("Please type some rough text first to polish.", icon=":material/warning:")
                else:
                    with st.spinner("Enhancing draft with Groq AI..."):
                        polished = service.polish_email_draft(compose_text, tone=polish_tone.lower())
                        st.session_state["compose_body_text"] = polished
                        st.toast("Draft polished successfully!", icon=":material/auto_awesome:")
                        st.rerun()

        with act_col2:
            if st.button(":material/send: Send Email", type="primary", width="stretch"):
                if not comp_to or not comp_subject or not compose_text.strip():
                    st.error("Please provide recipient, subject, and body.", icon=":material/error:")
                else:
                    with st.spinner("Sending email..."):
                        service.send_new_email(to=comp_to, subject=comp_subject, body=compose_text)
                    st.toast(f"Email sent successfully to {comp_to}!", icon=":material/check_circle:")
                    time.sleep(1)
                    st.rerun()

with tab_batch:
    st.markdown("### :material/auto_mode: Autonomous Batch Processor")
    st.caption("Scan incoming messages in bulk, extract key decisions, and stage replies in Gmail automatically.")

    with st.container(border=True):
        b_c1, b_c2, b_c3 = st.columns(3)
        with b_c1:
            batch_count = st.slider("Number of unread emails to process", min_value=1, max_value=15, value=5)
        with b_c2:
            batch_tone_opt = st.selectbox("Reply Tone", ["professional", "concise", "friendly"], index=0)
        with b_c3:
            direct_send = st.toggle("Direct Auto-Send (Bypass Drafts)", value=False, help="If OFF, replies are safely saved as Gmail Drafts for review.")

        if direct_send:
            st.warning("Caution: Direct auto-send is active. AI replies will be sent immediately to senders.", icon=":material/warning:")
        else:
            st.info("Safe Mode: AI replies will be created as Gmail Drafts in each conversation thread.", icon=":material/security:")

        if st.button(":material/play_arrow: Launch Batch Automation", type="primary", width="stretch"):
            with st.spinner("Processing batch pipeline with Groq AI..."):
                batch_results = service.process_batch(
                    query="is:unread",
                    limit=batch_count,
                    auto_send=direct_send,
                    tone=batch_tone_opt
                )

            st.toast(f"Batch completed! Processed {len(batch_results)} messages.", icon=":material/check_circle:")
            st.markdown("#### Processing Results")
            st.dataframe(batch_results, width="stretch")

with tab_analytics:
    st.markdown("### :material/bar_chart: Mailbox Intelligence Analytics")
    st.caption("Real-time telemetry and categorized email patterns extracted by Groq LLM.")

    if emails:
        categories = {}
        priorities = {"High": 0, "Medium": 0, "Low": 0}
        sentiments = {}

        for e in emails:
            an = e.get("analysis", {})
            cat = an.get("category", "Other")
            pri = an.get("priority", "Medium")
            sen = an.get("sentiment", "Neutral")

            categories[cat] = categories.get(cat, 0) + 1
            priorities[pri] = priorities.get(pri, 0) + 1
            sentiments[sen] = sentiments.get(sen, 0) + 1

        chart_c1, chart_c2 = st.columns(2)
        with chart_c1:
            with st.container(border=True):
                st.markdown("**:material/category: Email Categories Distribution**")
                st.bar_chart(categories, height=260)
        with chart_c2:
            with st.container(border=True):
                st.markdown("**:material/sentiment_satisfied: Sentiment Breakdown**")
                st.bar_chart(sentiments, height=260)

        with st.container(border=True):
            st.markdown("**:material/info: API Telemetry**")
            t1, t2, t3 = st.columns(3)
            with t1:
                st.metric("Active LLM Model", active_model, border=True)
            with t2:
                st.metric("Mailbox Account", user_email, border=True)
            with t3:
                st.metric("Processed Cache Size", f"{len(emails)} items", border=True)
    else:
        st.info("No email data cached for analytics. Refresh your inbox to populate charts.", icon=":material/info:")
