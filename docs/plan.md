## Project 1: AI Inbox & CRM Automation

**Goal:** Automate inbound lead/admin handling: classify messages, extract customer details, draft replies, create CRM records, and generate follow-up tasks.

**Why this belongs in the portfolio:** This is the clearest “AI automation services” demo. It is easy for recruiters, small businesses, and hiring managers to understand because it maps directly to wasted admin time.

**Target users:** Small sales teams, consultants, recruiters, agencies, founders.

**MVP scope:**

- Inbound message form or mock inbox.
- AI classification: lead, support, partnership, spam, urgent.
- Entity extraction: name, company, email, need, budget/timeline if present.
- AI-drafted reply with editable human approval.
- CRM pipeline board: new, qualified, replied, follow-up, closed.
- Follow-up task creation with due date.
- Activity log showing what AI suggested and what the user approved.

**Recommended stack:**

- Frontend: React, Tailwind CSS.
- Backend: FastAPI, Pydantic.
- Data: PostgreSQL or MongoDB.
- AI: OpenAI or Claude API.
- Background work: simple FastAPI background tasks first; Celery/RQ later only if needed.
- Integrations: start with mock CRM; optional Airtable/HubSpot later.

**Data model:**

- `Message`: raw content, sender, source, received time.
- `Lead`: contact fields, company, status, score.
- `AiAnalysis`: category, extracted fields, confidence, reasoning summary.
- `DraftReply`: generated text, edited text, approval status.
- `Task`: title, owner, due date, linked lead.
- `AuditEvent`: action, timestamp, actor, AI/user source.

**Demo flow:**

1. User submits or selects a messy inbound enquiry.
2. System classifies it and extracts CRM fields.
3. Dashboard shows suggested reply and follow-up task.
4. User edits/approves the reply.
5. Lead moves through the CRM pipeline.

**Portfolio case-study angle:**

- Problem: repetitive inbox triage and CRM data entry.
- Trade-off: AI suggests actions, but humans approve external communication.
- Outcome: reduces manual admin while preserving review and auditability.

**Stretch features:**

- Gmail/Outlook mock integration.
- HubSpot or Airtable sync.
- Lead scoring.
- Reply tone selector.
- SLA timer for urgent messages.
- Evaluation set with sample messages and expected classifications.

More details of the plan in following file: .cursor\plans\ai_inbox_crm_c3354398.plan.md