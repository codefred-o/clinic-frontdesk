# Clinic Front Desk — WhatsApp bot for Nigerian clinics

A FastAPI webhook server that connects the **WhatsApp Cloud API** to an LLM
acting as the virtual front desk for one or more clinics. It answers clinic
questions and books/reschedules/cancels appointments. Booking confirmations are
still **faked** in this milestone — the LLM produces the confirmation card
inline; real bookings arrive in M2 (see `docs/PRD.md`).

## Architecture

```
WhatsApp Cloud API  →  POST /webhook  →  clinic registry (by phone_number_id)
                                       →  conversation store (clinic, phone)
                                       →  LLM (prompt rendered from clinic YAML)
                                       →  send reply via the clinic's number
                       GET  /webhook  →  verify-token handshake
```

- `clinics/*.yaml` — one file per clinic: identity, hours, doctors, services + prices,
  HMOs, policies, and the clinic's WhatsApp `phone_number_id`. The Sunrise Dental
  demo clinic lives in `clinics/sunrise-dental.yaml`.
- `src/app/models/clinic.py` — the schema those files must match (unknown keys are rejected).
- `src/app/services/registry.py` — loads the directory at startup and resolves inbound
  messages to a clinic. Startup fails if the directory is missing or empty.
- `src/app/prompts.py` — the behaviour rules (fixed) plus the `CLINIC PROFILE` block
  rendered from the clinic config.
- `src/app/services/llm.py` — async LLM call
- `src/app/services/whatsapp.py` — async outbound sender (per-clinic number and token)
- `src/app/services/conversation.py` — in-memory history keyed by `(clinic_id, phone)`;
  lost on restart. Single process only.
- `src/app/routes/webhook.py` — verification + inbound message handling

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # then fill in your tokens
```

## Adding a clinic

1. Copy `clinics/sunrise-dental.yaml` to `clinics/<clinic-id>.yaml`.
2. Edit every field. `id` must be lowercase letters, digits, and hyphens.
3. Set `phone_number_id` to the id Meta shows for that clinic's number in WhatsApp
   Manager. If the number uses a different access token, set `whatsapp_token`.
4. Restart the server. It logs `Loaded N clinic config(s)` on startup.

All numbers under one Meta app share one webhook URL, so one running server
serves every clinic in the directory. A directory with a single file is the
single-clinic deployment.

## Run

```bash
uvicorn app.main:app --reload --app-dir src
```

Expose it for WhatsApp (e.g. ngrok), then register the webhook URL in the Meta
App dashboard using the same `WHATSAPP_VERIFY_TOKEN` you set in `.env`.

```bash
ngrok http 8000
```

## Test

```bash
pytest
ruff check .
```

## Demo script

1. "This is a fictional clinic. Try to stump it."
2. "Ask the price of a root canal." → instant, correct answer.
3. "Ask if they take your HMO." → handled.
4. "Now book an appointment for Saturday." → full booking flow + confirmation card.
5. Closer: "Imagine that's your clinic, answering at 11pm while you sleep."
