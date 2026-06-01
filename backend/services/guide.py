"""Build system prompts from guide_config."""

import json

from config import get_data_dir
from db import repository


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
