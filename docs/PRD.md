# PRD — Clinic Front Desk v1

**Product:** A WhatsApp front-desk service for Nigerian clinics — answers patient enquiries instantly, 24/7, and takes real appointments.
**Status:** Draft for sign-off · 2026-08-25
**Repo baseline:** FastAPI webhook demo for the fictional Sunrise Dental & Family Clinic (single-tenant, fake bookings, in-memory only). 26 tests passing, ruff clean.

---

## 1. Problem & goal

Nigerian clinics run patient communication on WhatsApp. Enquiries about prices, hours, HMO coverage, and appointments go unanswered whenever the front desk is busy or closed — evenings, Sundays, mid-rush — and each unanswered message is a patient who books elsewhere.

**v1 goal:** one always-on, multi-clinic deployment that (a) answers clinic questions accurately from a per-clinic profile, (b) books, reschedules, and cancels appointments *for real* — persisted to a database and pushed to the clinic's staff WhatsApp — and (c) is live enough that a cold-outreach message can include a demo number a clinic owner can text at 11pm and be convinced by.

**Business model for v1:** service-shaped, not self-serve. First 2–3 clinics are onboarded concierge-style (operator does the Meta setup and writes the config), billed manually (Paystack payment links). Automation of onboarding/billing waits until those clinics retain.

## 2. Users

| User | Role in v1 |
|---|---|
| **Clinic owner** | Buyer. Judges the bot by texting it themselves; receives the pitch. |
| **Front-desk staff** | Receives booking/handoff notifications on the clinic's staff WhatsApp number; takes over paused conversations. |
| **Patients** | Message the clinic's WhatsApp number; never know or care what's behind it. |
| **Operator (us)** | Runs the deployment, onboards clinics, receives error alerts. |

## 3. v1 features

### F1 — Multi-tenant clinic registry

One deployment serves many clinics. Rationale: Meta delivers all phone numbers under one app to a **single webhook URL**, and the concierge onboarding path puts clinic numbers on the operator's WABA — so inbound routing is required regardless; per-clinic deploys would need it too.

- Per-clinic YAML config files on the persistent volume: clinic id, display name, address, phone, hours, doctors, services + prices, HMOs, payment/cancellation policies, `phone_number_id`, staff notification number, optional per-clinic WhatsApp access token (defaults to the shared app token).
- `src/app/prompts.py` becomes a **template**: the behavior rules (tone, hard rules, booking flow, demo behaviors) stay fixed; the `CLINIC PROFILE` block is rendered from the clinic's config. Sunrise Dental becomes just the demo clinic's YAML.
- Inbound routing: parse `value.metadata.phone_number_id` from the webhook payload (add `metadata` to the `Value` model in `src/app/models/whatsapp.py`, which currently ignores it) and resolve the clinic. Unknown `phone_number_id` → log and return 200.
- `ConversationStore` keyed by `(clinic_id, phone)` instead of phone alone.
- **Degenerate-case guarantee:** a deployment with exactly one clinic config behaves identically — a dedicated single-clinic instance stays possible without a code fork.

*Acceptance:* two clinic configs loaded; a message to clinic A's number answers with A's prices and never B's; a one-config deployment passes the same test suite.

### F2 — Real bookings (LLM tool-calling → SQLite → staff WhatsApp)

Bookings stop being theater. The LLM gets tools instead of only prose:

- Tools: `book_appointment`, `reschedule_appointment`, `cancel_appointment` — structured fields: patient name, service, day/date/time, new-or-returning, phone (from sender).
- On `book_appointment`: insert a row in SQLite (`bookings` table: id, clinic_id, patient phone, name, service, slot, status, created_at), send the confirmation card to the patient, and **notify the clinic's staff number** ("front desk phone buzzes" is the demo's closing moment).
- Reschedule/cancel update the row's slot/status and notify both parties.
- **Staff notifications must be approved template messages, not free-form text.** WhatsApp permits free-form sends only within 24h of the recipient's last inbound message; the staff number never messages the bot, so free-form sends to it would be rejected. Templates (e.g. `new_booking`, `booking_changed`) are approved **once per WABA** and cover every clinic under it — one-time setup, billed per send.
- `LLMClient.reply()` (`src/app/services/llm.py:19`, today a single-shot completion) becomes a tool-execution loop: call → execute tool → feed result back → final patient-facing message.
- SQLite lives on the persistent volume; every query is `clinic_id`-scoped.
- The confirmation card's "You'll receive a reminder a day before" line is **removed/reworded** — v1 sends no automated reminders; staff remind manually from the notification.
- Extraction-reliability mitigation: the card is always echoed back to the patient, so a wrong field is visible and correctable in-chat ("that should be Saturday, not Friday").

*Acceptance:* a scripted booking conversation produces exactly one SQLite row with correct fields, one patient card, one staff card; reschedule and cancel mutate that row; restart loses no bookings.

### F3 — Robustness & safety

A service is responsible for someone's front desk. Silent failure is the worst outcome.

1. **No silent failures:** on any processing exception (`src/app/routes/webhook.py:55` currently swallows and goes mute), the patient receives the fallback "I'll connect you with our front desk team — they'll reply here shortly," and the error is logged.
2. **Non-text messages** (voice notes, images — very common on Nigerian WhatsApp) get a polite "I can only read text messages for now 🙂 — please type your question" instead of being dropped.
3. **Minimal human handoff:** a `handoff` tool call → staff number notified (via approved template, per F2's window rule) with the conversation context → bot replies paused for that `(clinic_id, phone)` for a configurable window (default 4h). Makes the prompt's existing "then stop responding" promise real. Uses M2's tool-calling loop.
4. **Webhook authenticity:** verify `X-Hub-Signature-256` (HMAC with the Meta app secret — new `whatsapp_app_secret` setting in `src/app/config.py`) on POST /webhook — the URL is public and there is a paid LLM behind it.
5. **Throttle:** simple per-sender rate limit (e.g. max N messages/minute) to cap abuse cost.
6. **Demo profile hygiene:** replace the `0803 XXX XXXX` placeholder with a plausible number — it currently appears verbatim in the emergency-escalation message.

*Acceptance:* fault-injection tests for 1–5 (LLM raises → fallback sent; image payload → polite reply; handoff pauses subsequent replies; bad signature → 403; burst → throttled). Existing 26 tests updated, suite green.

### F4 — Deployment & ops

- Always-on deploy to a cheap PaaS (Railway / Render / Fly) with a stable HTTPS URL and a persistent volume (SQLite + clinic configs).
- `/health` (already exists in `src/app/main.py`) wired as the platform health check.
- Structured logs; processing errors additionally alert **the operator** — via email or an approved WhatsApp template (free-form sends to the operator's number hit the same 24h-window rule as staff notifications) — clinics' uptime is now our liability.
- Single process/worker documented as a v1 constraint (in-memory conversation state + SQLite); multi-worker is the v2 trigger, not a v1 bug.

*Acceptance:* deployed URL passes Meta webhook verification; a real WhatsApp message round-trips in production; kill-and-restart keeps bookings and clinic configs.

### F5 — Outreach kit

- **Live demo clinic:** Sunrise Dental config on a real WhatsApp number, running on the production deploy — the number goes in the outreach message.
- **Demo video/GIF:** 30–60s screen recording of a real booking flow (enquiry → price answer → booking → staff phone notification), for owners who won't text an unknown number.
- **Cold-message templates:** 2–3 short variants (WhatsApp-first, email fallback) committed under `docs/outreach/`, each ending with the demo number CTA.

*Acceptance:* the three artifacts exist; one full demo conversation performed end-to-end on the live number.

## 4. Explicitly out of scope for v1

- Self-serve clinic onboarding / signup
- Billing integration (manual Paystack links only)
- Admin dashboard or any web UI
- Calendar / EMR / practice-management integrations
- Automated appointment reminders
- Voice-note transcription
- Analytics/reporting
- Multi-worker / horizontal scaling

Each is a v2 candidate gated on: ≥2 clinics retained and paying.

## 5. Service & onboarding notes

- **Concierge onboarding runbook** (to be written during M4): provision number on operator's WABA → Meta display-name approval → write clinic YAML → test conversation → go live. Notification templates (`new_booking`, `booking_changed`, `handoff_alert`, operator alert) are submitted for approval **once**, on the operator's WABA, before the first clinic — they cover all clinics under it. Expect days of Meta lag per clinic; set owner expectations in the close.
- **WABA ownership:** default = operator's WABA (fast, we control it). A clinic may bring its own Meta business later — that's the dedicated-instance path F1's degenerate case preserves. Open decision, revisit at clinic #3.
- **Data protection (NDPR posture):** minimal data by design — name, phone, service, 2–3-word reason; the prompt's existing privacy rule (no medical history, no test results) stays a hard rule; all rows `clinic_id`-scoped. Formal review before any clinic with its own compliance requirements.

## 6. Success metrics

- **Reliability:** zero silent failures — every inbound text message gets *some* reply (answer, fallback, handoff notice, or one throttle notice), except follow-ups during an active handoff pause or throttle window, which are deliberately suppressed; demo number answers 24/7.
- **Speed:** booking round-trip (patient confirmation + staff notification) < 15s.
- **Outreach (user to set targets):** N cold messages sent → ≥ X demo conversations started → ≥ 1 clinic in concierge onboarding. Suggested starting targets: N = 30, X = 5.

## 7. Milestones

| # | Milestone | Delivers | Depends on |
|---|---|---|---|
| M1 | Multi-tenant foundation | F1 (registry, prompt template, routing, keyed conversations) | — |
| M2 | Real bookings | F2 (tools, SQLite, staff notification) | M1 |
| M3 | Robustness & safety | F3 (fallback, non-text, handoff, signature, throttle) | M1; M2 for the handoff tool |
| M4 | Deploy + outreach kit | F4, F5 (PaaS, live demo clinic, video, templates, runbook) | M2, M3 |

Every milestone keeps `pytest` and `ruff check .` green and updates the existing suite (current tests assume single-tenant shapes and will change in M1/M2). Each milestone gets its own implementation plan before coding.

## 8. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Meta onboarding lag per clinic (verification, display-name approval) | Slows every close | Concierge runbook, expectations set in pitch; start Meta process at verbal yes |
| LLM mis-extracts booking fields via tool call | Wrong appointment recorded | Card always echoed to patient for correction; staff notification doubles as human check |
| Single-process constraint (in-memory conversations, SQLite) | Caps scale | Fine at v1 volume; documented as the v2 trigger |
| One bad deploy breaks *all* clinics' front desks | Churn | Staged deploy (demo clinic first), operator error alerts, `/health` checks |
| Prompt drift breaks clinic facts | Wrong prices quoted | Existing prompt-integrity tests generalized to per-clinic profile rendering in M1 |
| Template approval delayed or rejected by Meta | Staff notifications blocked — bookings persist but nobody is told | Submit templates at the very start of M2; fallback: operator relays bookings manually from SQLite until approval lands |
