# Sunrise Dental — WhatsApp Front Desk Demo Bot

A thin FastAPI webhook server that connects the **WhatsApp Cloud API** to an
LLM acting as the virtual front desk for the (fictional) *Sunrise Dental &
Family Clinic*. It answers clinic questions and books/reschedules/cancels
appointments. Booking confirmations are **faked** — the LLM produces the
confirmation card inline; there is no real calendar.

## Architecture

```
WhatsApp Cloud API  →  POST /webhook  →  conversation store  →  LLM  →  send reply (Graph API)
                       GET  /webhook  →  verify-token handshake
```

- `src/app/prompts.py` — the system prompt + clinic profile (single source of truth)
- `src/app/services/llm.py` — async LLM call
- `src/app/services/whatsapp.py` — async outbound message sender
- `src/app/services/conversation.py` — in-memory per-user history (lost on restart; fine for a demo)
- `src/app/routes/webhook.py` — verification + inbound message handling

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # then fill in your tokens
```

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
```

## Demo script

1. "This is a fictional clinic. Try to stump it."
2. "Ask the price of a root canal." → instant, correct answer.
3. "Ask if they take your HMO." → handled.
4. "Now book an appointment for Saturday." → full booking flow + confirmation card.
5. Closer: "Imagine that's your clinic, answering at 11pm while you sleep."
