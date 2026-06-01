# Email Triage Classification Guide

This document is the **policy** the AI follows to sort emails — the "rules
without rules". `services/guide.py:build_system_prompt()` loads this file plus
the `label_schema` from `phase_1_email_triage_examples.json` and turns it into
the system prompt. Edit this file to change triage behaviour; you should not
need to change code.

> Status: STARTER STUB. Fill in the definitions and rules below, then test them
> against `phase_1_email_triage_examples.json`.

## How to classify (high level)

Read the subject and body together, then decide three things:

1. **category** — what kind of email it is.
2. **priority** — how urgently a human must act.
3. **suggested_action** — the recommended next step (a human can override).

Always return a short, factual `reason`. Never invent facts that are not in the
email.

## Category definitions

- **human** — written by a person who expects a response or action.
  - TODO: clarifying notes / examples.
- **machine_generated** — automated output (alerts, health checks, reports).
  - TODO: clarifying notes / examples.
- **event** — invitations, social/calendar items, announcements.
  - TODO: clarifying notes / examples.
- **spam** — unsolicited / irrelevant / promotional with no business value.
  - TODO: clarifying notes / examples.

## Priority rules

- **urgent_action** — trading/production/client impact, failures, or explicit
  urgency. TODO: refine.
- **non_urgent_action** — a real request, but no time pressure. TODO: refine.
- **ignore** — nothing to do (e.g. an all-green health check). TODO: refine.

## Suggested action mapping

Describe when to choose each: `acknowledge`, `escalate`, `archive`, `ignore`,
`ask_human`. TODO: write the decision rules and any tie-breakers.

## Output contract

Respond with **only** a JSON object, no prose, matching:

```json
{
  "category": "<one of the allowed category values>",
  "priority": "<one of the allowed priority values>",
  "reason": "<one short sentence grounded in the email>",
  "suggested_action": "<one of the allowed suggested_action values>"
}
```

The exact allowed values are injected from `label_schema` at prompt-build time,
so this guide and the code can never disagree on labels.
