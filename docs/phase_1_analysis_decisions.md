# Phase 1 Product Spec: AI Inbox Triage

# Problem Statement

In an equities trading support environment, the support team receives a high volume of mixed-priority emails throughout the day. These emails include urgent trading investigation requests, outage notifications, developer requests, machine-generated health checks, event invitations, wiki updates, and Jira notifications.

Today, the team has to manually scan the inbox to decide which messages need immediate action, which can wait, and which can be ignored. This manual triage wastes time and increases the risk of missing a business-critical incident.

# User And Context

The primary user is an equities support analyst who monitors a shared support inbox during the trading day. Timing matters because trading issues, failed checks, order problems, and outage notifications may require fast acknowledgement, escalation, or investigation.

The inbox is noisy because operational messages are mixed with low-value notifications. The product should help the analyst focus on messages that need attention without removing human control from risky actions.

# Current Workflow

1. Emails arrive in a shared support inbox.
2. A support analyst manually reads the subject and body.
3. The analyst decides whether the message is urgent, non-urgent, informational, or safe to ignore.
4. If action is required, the analyst decides whether to acknowledge, investigate, escalate, archive, or wait for more information.

# Pain Points

- Urgent trading or production issues can be hidden among low-value notifications.
- Machine-generated emails create noise, especially when most checks are green.
- Manual triage takes time away from investigation and incident response.
- Different analysts may classify similar messages differently.
- Some actions, such as client acknowledgement or command execution, are too risky to automate without approval.

# Product Goal

Phase 1 should classify inbound emails, assign a priority, explain the reasoning, and suggest the next action. The AI should help the analyst triage faster, but it should not send external replies, run commands, or escalate incidents without human approval.

# Classification Model

The AI should classify each email across three separate dimensions:

- `category`: what type of message it is.
- `priority`: how quickly a human should care about it.
- `suggested_action`: what should happen next.

Separating these dimensions is important because one category can have different priorities. For example, a machine-generated health check can be urgent when a check fails, but ignorable when all checks are green.

## Categories

| Category | Meaning | Examples |
| --- | --- | --- |
| `human` | A message written by a person asking for help, information, or action. | Trader issue, client request, developer request, incident update. |
| `event` | A social, charity, community, team, or business-line event message. | Drinks invitation, charity event, team event. |
| `spam` | Low-value or unrelated message that does not need support action. | Advertisement, generic update, irrelevant notification. |
| `machine_generated` | Automated system, script, monitoring, wiki, or Jira notification. | Health check, script output, Jira update, wiki update. |

## Priorities

| Priority | Meaning | Examples |
| --- | --- | --- |
| `urgent_action` | A human should review quickly because there may be business, trading, client, or production impact. | Failed trade, failed health check, timeout, outage, rollback request. |
| `non_urgent_action` | A human should review, but it is not immediately business-critical. | Developer asks for stats, script output needs checking, event may be relevant. |
| `ignore` | No support action is required. | Green health check, passed checks, routine notification, advertisement. |

## Suggested Actions

| Suggested action | Meaning |
| --- | --- |
| `acknowledge` | Prepare an acknowledgement message for human approval. |
| `escalate` | Recommend escalation or investigation by the support team. |
| `archive` | Suggest moving the message out of the active inbox. |
| `ignore` | Suggest no action. |
| `ask_human` | Ask a human to decide because the message is ambiguous or risky. |

# AI Output Contract

For every inbound email, the AI should return a structured result:

```json
{
  "category": "human | event | spam | machine_generated",
  "priority": "urgent_action | non_urgent_action | ignore",
  "reason": "Short explanation of why the email was classified this way.",
  "suggested_action": "acknowledge | escalate | archive | ignore | ask_human"
}
```

The `reason` field matters because support analysts need to trust the result. A useful reason should mention the signal that drove the decision, such as a failed check, timeout, trading issue, command request, or all-green health status.

# Example Emails And Expected Classifications

## 1. Human - Urgent Trading Investigation

Subject: VOD.L stock stopped trading
Contents:
Hi team,

Why did this POV order stop trading before market close?
It was supposed to trade on MOC - PUKOID3234234234

Regards,
Trader

Expected AI output:

```json
{
  "category": "human",
  "priority": "urgent_action",
  "reason": "The sender reports that an order stopped trading before market close, which could indicate trading or client impact.",
  "suggested_action": "acknowledge"
}
```

## 2. Human - Non-Urgent Developer Request

Subject: <instance> stats check request

Hi team,

Can you run this admin command on <instance>?

admincmd <cmd>

admincmd <cmd2>

please paste me the output thx

Regards,
Dev

Expected AI output:

```json
{
  "category": "human",
  "priority": "non_urgent_action",
  "reason": "A developer is asking support to run admin commands and return the output, but there is no incident or trading impact mentioned.",
  "suggested_action": "ask_human"
}
```

## 3. Event - Charity Invitation

Subject: You are invited for competitive darts for good cause

Hi,

We are hosting a social event where we invite you to compete in playing darts!

This event money will all go to charity

We are organising this event at <dart place location and name>
Will take place on June 11th

Click this link if you would like to join <link>

Thanks,
Event organising team

Expected AI output:

```json
{
  "category": "event",
  "priority": "non_urgent_action",
  "reason": "The email is an invitation to a charity social event and does not require production support investigation.",
  "suggested_action": "archive"
}
```

## 4. Machine Generated - Urgent Health Check

Subject: <System Name> - SOD Health Checks

Check timestamp: 07:05:00 - 30/04/2026
--------------------------------------------
| Instance    | Status | Response Time     |
| <instance1> | OK     | 2s - 07:05:02     |
| <instance2> | OK     | 2s - 07:05:02     |
| <instance3> | FAIL   | Timeout after 30s |
--------------------------------------------

Expected AI output:

```json
{
  "category": "machine_generated",
  "priority": "urgent_action",
  "reason": "One instance failed the start-of-day health check with a timeout, which may indicate a production readiness issue.",
  "suggested_action": "escalate"
}
```

## 5. Machine Generated - Green Health Check

Subject: <System Name 2> - SOD Health Checks

Check timestamp: 07:05:00 - 29/04/2026
--------------------------------------------
| Instance    | Status | Response Time     |
| <instance1> | OK     | 2s - 07:05:02     |
| <instance2> | OK     | 3s - 07:05:03     |
| <instance3> | OK     | 2s - 07:05:02     |
--------------------------------------------

Expected AI output:

```json
{
  "category": "machine_generated",
  "priority": "ignore",
  "reason": "All listed instances passed the health check, so no support action is required.",
  "suggested_action": "ignore"
}
```

# Decision rules

Use these rules to guide the first version of the classifier:

- If a message mentions an urgent request, investigation, failed trade, order cancellation, timeout, outage, client impact, production impact, rollback, or incident, classify it as `urgent_action`.
- If a developer asks support to run a command, check stats, collect history, review logs, or paste output, classify it as `non_urgent_action` unless the message also mentions an incident or production impact.
- If a machine-generated health check contains `FAIL`, `CRITICAL`, `ERROR`, timeout, or bad status signals, classify it as `urgent_action`.
- If all health checks are green, passed, or OK, classify it as `ignore`.
- If the message is about a social, charity, community, or team event, classify it as `event`.
- If the message is an advertisement, generic wiki update, routine Jira notification, or unrelated exchange update, classify it as `spam` or `machine_generated` with priority `ignore`.
- If the classifier is uncertain or the suggested action could affect a client or production system, use `ask_human`.

# Human-In-The-Loop Rules

The AI may classify emails and suggest actions automatically, but a human must approve any action that could affect clients, production systems, or incident handling.

Human approval is required before:

- Sending an external reply or client acknowledgement.
- Running an admin command or script.
- Escalating an incident to another team.
- Closing, archiving, or suppressing a message that might involve trading, client, or production impact.
- Sharing command output, logs, or internal system details with a requester.

Example: if a trader asks why an order stopped trading, the AI can suggest an acknowledgement, but the support analyst must approve the message before it is sent.

# Out Of Scope For Phase 1

Phase 1 will not:

- Connect to a live email inbox.
- Send replies automatically.
- Run commands or scripts.
- Create or update CRM records.
- Create or update Jira tickets.
- Escalate incidents automatically.
- Learn from user feedback automatically.

# Success Criteria

Phase 1 is complete when:

- The project has a clear product problem, target user, workflow, and pain points.
- Each sample email has an expected `category`, `priority`, `reason`, and `suggested_action`.
- The classifier can explain why it chose a classification.
- Urgent trading, outage, failed check, and client-impact messages are not classified as `ignore`.
- Green health checks and routine low-value notifications can be safely classified as `ignore`.
- Any action involving external replies, commands, escalation, or client acknowledgement requires human approval.
- The spec is clear enough to create a small test dataset and implement the first version of the classifier.

# Interview Explanation

The main design decision is to separate message type from urgency. `category` describes what the email is, `priority` describes how quickly a human should care, and `suggested_action` describes what should happen next. This makes the system easier to test, safer to extend, and clearer for a support analyst to trust.