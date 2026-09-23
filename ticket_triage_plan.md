# Project: Intelligent Ticket Routing Agent

## Context for Claude Code

I am building a portfolio project to demonstrate applied agentic AI engineering for
Applied AI Engineer / Forward Deployed Engineer job applications — real tool-calling,
retrieval-augmented reasoning, and a confidence-aware escalation pattern, backed by a
production-shaped backend (FastAPI, Redis, Langfuse, Docker) and a small demo frontend.
This is my third portfolio project, following a production RAG system and "ReviewCrew" (a
multi-agent LangGraph code-review system with MCP tool servers).

Please work with me iteratively, phase by phase. Confirm each phase works before moving to
the next, and explain design decisions as you go — especially the tool-use/confidence-gating
logic, since that's the main new pattern in this project versus my previous two.

## Goal

Build an agent that reads an incoming customer support ticket and decides what should
actually happen to it next — not just classify it, but reason using retrieved context
(similar past resolved tickets, the customer's account history) to decide whether to
auto-resolve, route to a specific team, or escalate to a human — and measure how well it
performs against real historical ticket-routing decisions.

## The core idea: agentic, not just classification

A plain classifier can label a ticket's category/urgency from the text alone — that's a
commodity, solved problem (fine-tuned classifiers for this already exist publicly). The
point of this project is that the agent's final decision must depend on **more than the raw
ticket text** — specifically, on what it finds when it looks up (a) similar past resolved
tickets and (b) the customer's account context. The same ticket text could legitimately
produce a different decision depending on what the agent discovers when it investigates —
that dependency on gathered evidence, not the text alone, is what makes this agentic.

## Architecture decision: one agent, multiple tools (not a multi-agent split)

Unlike ReviewCrew (where three genuinely different concerns — style, security, tests —
justified three separate agents), ticket triage is one continuous line of reasoning:
classify → decide if more info is needed → gather it via tools → decide again → final
action. Build this as a **single Triage Agent** with two tools and a LangGraph flow that
lets it call tools, reason over results, and loop before reaching a final decision. Do not
split this into multiple agent personas — it would add complexity without adding a real
capability here.

## Constraints (carried over from previous projects)

- **No model training/fine-tuning.** Prompting + tool calling + orchestration only.
- **Free LLM APIs, acceptable for local/testing use** (not "free forever" — one-time free
  credits are fine, since this is a portfolio project, not production). Primary: **Groq**
  (fast, generous free tier, good fit for this project's more real-time-feeling use case and
  higher call volume during eval). Secondary/fallback: **Gemini**. Keep the model provider
  swappable via config, exactly as in previous projects — don't hardcode it into agent logic.
- Before finalizing, do a quick side-by-side check of Groq vs. Gemini specifically on the
  hand-authored ambiguous demo scenario (see Phase 2) — the model that more honestly
  expresses uncertainty rather than confidently guessing is the better fit here, since
  confidence-gating is central to this project.

## Dataset

**Source:** "Multilingual Customer Support Tickets" (Tobias Bueck), available on Kaggle and
Hugging Face (`Tobi-Bueck/customer-support-tickets`). Use the file variant with exactly 16
columns (`aa_dataset-tickets-multi-lang-5-2-50-version.csv` or equivalent) — some other
variants of this dataset on Kaggle carry a different, larger column set; do not assume
they're interchangeable.

**Verified real schema (16 columns, confirmed by direct inspection):** `subject`, `body`,
`answer`, `type`, `queue`, `priority`, `language`, `version` (irrelevant — drop, ignore
entirely), `tag_1` through `tag_8`.

**Field details, confirmed against real data (28,587 total rows):**
- `body` = ticket text, no nulls, median ~377 chars, max ~1,147 chars — short, clean,
  workable size, no huge-thread problem to handle.
- `subject` = **has real nulls (3,838 of 28,587, ~13%)** — Phase 1's loading logic must
  explicitly handle this (fall back to using `body` alone when `subject` is null; do not
  assume it's always present).
- `answer` = the real historical resolution text, this is the corpus for the
  `search_past_tickets` RAG tool. **Has a small number of nulls (7 rows)** — explicitly
  drop rows with a null `answer` before using it as the RAG corpus, since an entry with no
  resolution is useless there.
- `type` = **Incident / Request / Problem / Change** (no nulls) — a real, useful ITSM-style
  field. Use this explicitly as part of the agent's decision output alongside `queue`, not
  as an afterthought.
- `queue` = 10 real categories, no nulls: Technical Support, Product Support, Customer
  Service, IT Support, Billing and Payments, Returns and Exchanges, Service Outages and
  Maintenance, Sales and Pre-Sales, Human Resources, General Inquiry. This is the primary
  routing-decision target.
- `priority` = low / medium / high (no nulls).
- `language` = `en` (16,338 rows) / `de` (12,249 rows). **Filter to `language == "en"` in
  Phase 1** — same scope-narrowing discipline as filtering to Python-only tickets in a
  previous project.
- `tag_1` = reliably populated (0 nulls), genuinely useful, more granular than `queue` —
  values include Security, Bug, Feedback, Feature, Performance, Billing, Outage, Network,
  Documentation, Product, Crash, and more. Use this as a secondary signal for the
  `search_past_tickets` tool and for eval.
- `tag_2` = also reliably populated (13 nulls out of 28,587) — usable alongside `tag_1`.
- **`tag_3` through `tag_8` are sparse and should NOT be relied on for anything.** Null
  counts confirmed: `tag_3` missing 136, `tag_4` missing 3,058, `tag_5` missing 14,042,
  `tag_6` missing 22,713, `tag_7` missing 26,547, `tag_8` missing in all but ~565 of 28,587
  rows. Only use `tag_1`/`tag_2` in the tool/eval design; ignore `tag_3`-`tag_8`.

**Note on text style (be accurate about this in the README):** the `body`/`answer` text
reads as polished, structured, template-like business-support emails (e.g. "Dear Customer
Support Team,\n\nI am writing to report...") rather than messy raw inbox text. This is
worth one honest line in the README rather than presenting it as if it were unfiltered
production data.

**What the dataset does NOT have, and must be synthetically generated:** there is no
customer ID linking multiple tickets to the same person, and no account-level context
(VIP status, prior ticket count, churn risk). This must be generated — see the Synthetic
Data Generation Plan below. Be explicit in the README about exactly which fields are real
vs. synthetic; this honesty is part of the project's credibility, not a detail to gloss
over.

## Synthetic Data Generation Plan

Generate this as **one deterministic, seeded script**, run once, producing a
`customer_profiles.json` that sits alongside the untouched raw dataset — never mix
generation logic into the raw dataset file itself.

1. **Generate a pool of ~50-80 synthetic customer IDs** via `Faker` (name, email — cosmetic
   fields only).
2. **Deterministically assign real tickets to these customer IDs** — most customers get 1
   ticket; a deliberate subset get 3-5 tickets clustered together (fixed random seed, so
   this is reproducible). This clustering is what gives the `get_customer_context` tool
   something real to find.
3. **Derive `prior_ticket_count` directly from the Step 2 assignment** — not generated
   independently. A customer with 4 tickets assigned to them has `prior_ticket_count: 4`,
   full stop — this is the "derived, not invented separately" discipline that keeps the
   synthetic layer internally consistent.
4. **Generate remaining profile fields as seeded synthetic**, clearly documented as such:
   `vip_tier` (mostly "standard," a minority "premium"), `account_age_days`, `churn_risk`.
5. **Hand-author 2-3 flagship demo scenarios explicitly, not left to chance:**
   - A VIP customer with a repeat issue on record → should trigger escalation even though
     the ticket text alone reads as routine.
   - A first-time customer with an issue matching a previously-resolved ticket → should
     auto-resolve confidently, citing the past resolution.
   - A genuinely ambiguous ticket → should trigger "not confident, escalate to human" —
     this is the scenario used for the Groq-vs-Gemini honesty check in the Constraints
     section above, and the one that proves the escalation path actually works, not just
     the happy path.
6. **Optionally generate a short, readable "internal account note" per customer via an LLM
   call** (e.g. *"Customer has raised billing concerns twice in the past quarter; previous
   resolution involved a partial refund"*) — this is a purely cosmetic, presentational field
   surfaced on the customer profile in the frontend/tool output. It is never used for eval
   scoring or the agent's actual decision logic, so its non-determinism doesn't matter. Its
   only purpose is making the demo feel more human/realistic when a profile card is viewed.
   Keep this step clearly separated from the deterministic fields above, and label it as
   LLM-generated flavor text in the README's real-vs-synthetic data table (a third category,
   alongside "real" and "deterministic synthetic").
7. Store outputs separately:
   ```
   data/
   ├── raw/
   │   └── support_tickets.jsonl       # untouched real dataset
   ├── synthetic/
   │   └── customer_profiles.json      # generated, seeded, reproducible
   └── generate_customer_profiles.py   # the one generation script
   ```
8. Document the real-vs-synthetic split as an explicit table in the README — three
   categories: real (dataset fields), deterministic synthetic (customer assignment,
   prior_ticket_count, vip_tier, etc.), and LLM-generated cosmetic (account notes).

## Architecture / Phases

Work through these phases in order. Get the core agent loop working end-to-end on a small
slice before scaling up to full eval or adding infra polish.

### Phase 1 — Environment & data setup
- Python environment; install `langchain`, `langgraph`, Groq's SDK and/or
  `langchain-google-genai`, `fastapi`, `uvicorn`, `redis`, `langfuse`, `faker`.
- Load the real dataset (16 real columns, verified schema — see Dataset section above).
  Filter to `language == "en"`, drop rows with null `answer`, handle null `subject` by
  falling back to `body` alone. Ignore `version` and `tag_3`-`tag_8` entirely.
- Run `generate_customer_profiles.py` (Synthetic Data Generation Plan above), verify the
  three hand-authored flagship scenarios are present and correctly constructed, and spot-check
  a few of the LLM-generated cosmetic account notes for sanity (readable, plausible, clearly
  separate from the deterministic fields).
- Carve out a dev/valid slice and a final held-out eval slice, same discipline as previous
  projects (small, manageable sizes — a few dozen to ~100 examples, not the full dataset).

### Phase 2 — Tools
- `search_past_tickets(query)` — RAG-style search over the real `body`+`answer` pairs from
  the dev/valid slice's ticket pool, returning similar past tickets and their real
  resolutions.
- `get_customer_context(customer_id)` — looks up the synthetic customer profile: vip_tier,
  prior_ticket_count, account_age_days, churn_risk.
- Test each tool independently before wiring into the agent.

### Phase 3 — Triage Agent (single agent, LangGraph tool-use loop)
- Build the LangGraph flow: read ticket → agent decides whether to call `search_past_tickets`
  and/or `get_customer_context` → agent reasons over what it finds → agent reaches a final
  decision: **auto-resolve** (with a cited past resolution), **route** (to a specific
  queue/team, matching the dataset's real `queue` categories, with `type` — Incident/
  Request/Problem/Change — as a secondary output field), or **escalate to human**.
- Every decision must include a short written justification — never a bare label.
- Implement explicit confidence-gating: the agent should recognize when it lacks enough
  signal to be confident and choose escalation over guessing.
- Test manually against the three hand-authored flagship scenarios first — confirm each
  produces the expected kind of decision (auto-resolve / escalate-due-to-VIP-repeat /
  escalate-due-to-ambiguity) before testing more broadly on the dev/valid slice.

### Phase 4 — FastAPI backend
- `POST /tickets` — submit a ticket (text + optional customer_id), returns a run ID.
- `GET /tickets/{id}/stream` — SSE stream of the agent's reasoning/tool calls as it works.
- `GET /tickets/{id}` — final structured decision (category, routing, confidence,
  justification).
- `GET /tickets` — list recent tickets with their outcomes (for the frontend to poll/consume).

### Phase 5 — Evaluation against real historical outcomes
- Run the held-out eval slice through the full pipeline.
- Compare the agent's routing decision against the dataset's real `queue`/`priority`/`type`
  fields — agreement rate, same measured-eval discipline as previous projects. Use `tag_1`/
  `tag_2` (the only reliably-populated tag fields) as a secondary, finer-grained eval signal
  where useful — do not rely on `tag_3` through `tag_8`, which are too sparse to use.
- Separately track escalation behavior: on the deliberately ambiguous cases, did it actually
  escalate rather than guess? This is as important a number to report as raw accuracy.
- Build as a repeatable script, save results for before/after comparison as the project
  evolves.

### Phase 6 — Redis caching + Langfuse observability
- Cache full decisions keyed on a normalized hash of ticket text (+ customer_id if present),
  avoiding redundant LLM calls on repeated/duplicate submissions.
- Trace every step (which tools were called, reasoning, final decision, confidence) in
  Langfuse; push Phase 5's eval scores into Langfuse for tracking over time.

### Phase 7 — Frontend: quick "vibe coded" demo dashboard
- Scope deliberately small — this is a demo aid, not a product build. A single-page
  React/Next.js app:
  - **Input box** — submit a new ticket (text, optional customer_id) to trigger the agent.
  - **Category columns (kanban-style)** — one column per queue/category; submitted tickets
    visually land in the column matching the agent's routing decision.
  - **A distinct "Needs Human Review" column** — for escalated tickets, so the escalation
    behavior is visibly demonstrated, not just the auto-resolve/route happy path.
  - Each ticket card shows the agent's confidence and one-line justification (click/expand
    for the full reasoning trace).
  - Consume the FastAPI SSE stream so tickets appear to "arrive" and route live, rather than
    requiring a manual page refresh.
- No auth, no user accounts, no settings — keep this to 3-4 components total. The point is a
  convincing, live demo of the routing/escalation behavior, not a polished product.

### Phase 8 — Docker deployment
- `docker-compose.yml`: FastAPI app, Redis, Langfuse (self-hosted or cloud, consistent with
  previous projects), and the frontend (as a separate service or static build served
  alongside).
- Confirm the full system runs via `docker compose up`, including the live demo flow from
  ticket submission through to visible routing on the dashboard.

## Suggested repo structure

```
ticket-triage-agent/
├── app/
│   ├── main.py                    # FastAPI app + routes
│   ├── agent/
│   │   ├── triage_agent.py        # single agent, LangGraph tool-use loop
│   │   └── graph.py
│   ├── tools/
│   │   ├── search_past_tickets.py
│   │   └── get_customer_context.py
│   ├── cache/                     # redis client + caching logic
│   ├── llm/                       # swappable provider config (Groq / Gemini)
│   └── observability/             # langfuse instrumentation
├── data/
│   ├── raw/                       # untouched real dataset
│   ├── synthetic/                 # generated customer profiles
│   └── generate_customer_profiles.py
├── eval/
│   ├── build_eval_slice.py
│   └── run_eval.py
├── frontend/                      # small Next.js/React dashboard
├── docker-compose.yml
├── Dockerfile
└── README.md                      # architecture, real-vs-synthetic data table, eval numbers
```

## Scope guardrails

- One agent, not multiple — resist the urge to split into separate classification/context/
  decision agents; that adds complexity without adding real capability here.
- Frontend stays intentionally small (3-4 components) — it's a demo aid, not a product.
- Don't skip the hand-authored flagship scenarios in favor of relying on random synthetic
  data to "happen to" produce a good demo case.
- Confidence-gating and escalation behavior are as important to get right and to measure as
  raw routing accuracy — don't treat escalation as an afterthought.

## Immediate next step

Start with Phase 1. Load the real dataset, confirm the fields, then build and verify
`generate_customer_profiles.py` — check that the three hand-authored flagship scenarios
(VIP repeat issue, first-time-matching-past-resolution, genuinely ambiguous) are correctly
constructed before moving to Phase 2.
