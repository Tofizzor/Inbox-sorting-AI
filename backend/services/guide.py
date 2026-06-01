"""Build system prompts from guide_config."""

import json

from config import get_data_dir
from db import repository
from models.classifier_models import EmailAnalysis, EmailInput

# Bump this when the reply prompt wording/structure changes so drafts are traceable
# to the prompt that produced them (recorded in the draft_created audit payload).
REPLY_PROMPT_VERSION = "reply-v1"

# The mock LLM provider keys off this phrase (in the reply system prompt) to return a
# deterministic reply instead of triage JSON. Keep it in sync with services/llm_client.
_REPLY_INTENT_MARKER = "drafting a reply"


def load_guide_config() -> dict:
    try:
        return repository.get_guide_config()
    except Exception:
        seed_path = get_data_dir() / "guide_config.json"
        return json.loads(seed_path.read_text(encoding="utf-8"))


def load_label_schema() -> dict:
    config = load_guide_config()
    return config.get("label_schema", {})


def build_system_prompt() -> str:
    config = load_guide_config()
    labels = config.get("label_schema", {})
    policy = config.get("policy", {})
    guide_text = config.get("guide_text", "")

    schema_example = {
        "category": "one of: " + ", ".join(labels.get("category", [])),
        "priority": "one of: " + ", ".join(labels.get("priority", [])),
        "suggested_action": "one of: " + ", ".join(labels.get("suggested_action", [])),
        "reason": "one short sentence grounded in the email",
        "extracted_fields": {
            "order_ids": ["string"],
            "instance_names": ["string"],
            "error_summary": "string or null",
            "sender_name": "string or null",
            "detected_keywords": ["string"],
        },
    }

    policy_lines = []
    for key, rules in policy.items():
        if isinstance(rules, dict):
            policy_lines.append(f"{key}:")
            for name, desc in rules.items():
                policy_lines.append(f"  - {name}: {desc}")
        elif isinstance(rules, list):
            policy_lines.append(f"{key}:")
            for item in rules:
                policy_lines.append(f"  - {item}")
        else:
            policy_lines.append(f"{key}: {rules}")

    return f"""You are an email triage agent for a support inbox.

{guide_text}

Policy:
{chr(10).join(policy_lines)}

Rules:
- Read subject and body together.
- Return ONLY valid JSON matching this shape (no markdown, no extra text):
{json.dumps(schema_example, indent=2)}
- Do NOT include a "destination" field; routing is computed server-side.
- Use only the allowed enum values for category, priority, and suggested_action.
- extracted_fields must reflect what is actually in the email; use empty lists/null when unknown.
"""


def build_reply_system_prompt(tone: str = "professional") -> str:
    """System prompt for the SEPARATE reply-drafting LLM call (version-tagged).

    The model only produces text; it never decides whether the reply is sent. The
    draft is always reviewed and approved by a human before anything leaves the system.
    """
    config = load_guide_config()
    guide_text = config.get("guide_text", "")
    policy = config.get("policy", {})
    summary = policy.get("summary", "") if isinstance(policy, dict) else ""

    return f"""You are a customer support agent {_REPLY_INTENT_MARKER} to an inbound email.
Prompt version: {REPLY_PROMPT_VERSION}

Context guide:
{summary}
{guide_text}

Write a SHORT reply (a few sentences) in a {tone} tone.
Rules:
- This is a DRAFT a human will review, edit, and approve before it is ever sent.
- Do NOT invent facts, order numbers, dates, refunds, or commitments not present in the email.
- Acknowledge the customer's issue and state the next step at a high level only.
- Do not sign with a real person's name; sign generically (e.g. "Support Team").
- Return ONLY valid JSON in this exact shape (no markdown, no extra keys):
{{"reply": "<the reply text>"}}
"""


def build_reply_user_prompt(email: EmailInput, analysis: EmailAnalysis) -> str:
    """User prompt: the customer's email plus triage context for grounding the reply."""
    fields = analysis.extracted_fields
    lines = [
        f"Customer email subject: {email.subject}",
        "Customer email body:",
        email.body.strip(),
    ]
    if email.sender:
        lines.append(f"Sender: {email.sender}")
    lines.append("")
    lines.append("Triage analysis (context only — do not quote verbatim):")
    lines.append(f"- category: {analysis.category.value}")
    lines.append(f"- priority: {analysis.priority.value}")
    lines.append(f"- suggested_action: {analysis.suggested_action.value}")
    lines.append(f"- reason: {analysis.reason}")
    if fields.order_ids:
        lines.append(f"- order_ids: {', '.join(fields.order_ids)}")
    if fields.error_summary:
        lines.append(f"- error_summary: {fields.error_summary}")
    lines.append("")
    lines.append('Draft the reply now as JSON: {"reply": "..."}')
    return "\n".join(lines)
