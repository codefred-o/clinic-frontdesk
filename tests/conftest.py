"""Shared fixtures: a TestClient with fake LLM and WhatsApp services on app.state."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

# Deterministic settings before the app/settings cache is built.
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "test-verify-token")
os.environ.setdefault("LLM_API_KEY", "test-key")

from app.config import get_settings  # noqa: E402
from app.main import app  # noqa: E402

VERIFY_TOKEN = "test-verify-token"

from pathlib import Path  # noqa: E402

from app.models.clinic import ClinicConfig, Doctor, Service  # noqa: E402
from app.services.registry import ClinicRegistry, load_clinic_file  # noqa: E402

SUNRISE = load_clinic_file(Path("clinics/sunrise-dental.yaml"))
SUNRISE_PHONE_NUMBER_ID = SUNRISE.phone_number_id

# A second, deliberately different clinic so tests can prove isolation.
GREENFIELD = ClinicConfig(
    id="greenfield-medical",
    name="Greenfield Medical Centre",
    short_name="Greenfield",
    area="Lekki Phase 1, Lagos",
    address="5 Admiralty Way, Lekki Phase 1, Lagos",
    phone="0701 000 0000",
    hours="Mon–Sat 8:00am–8:00pm · Sun 10:00am–4:00pm",
    lead_doctor="Dr. Tunde",
    doctors=[Doctor(name="Dr. Tunde Bakare", role="Medical Director")],
    services=[
        Service(name="General Consultation", price="15,000"),
        Service(name="Malaria Test", price="5,000"),
    ],
    payment="Cash, transfer, POS.",
    hmos=["Avon HMO"],
    cancellation_policy="free up to 12h before.",
    first_visit="bring a valid ID.",
    phone_number_id="222000000000000",
    staff_phone="2347010000000",
)
GREENFIELD_PHONE_NUMBER_ID = GREENFIELD.phone_number_id


class FakeLLM:
    """Records the history and system prompt it was given and returns a canned reply."""

    def __init__(self, reply: str = "Good morning! How can I help? 🙂") -> None:
        self.reply_text = reply
        self.calls: list[list[dict[str, str]]] = []
        self.system_prompts: list[str] = []

    async def reply(self, history: list[dict[str, str]], system_prompt: str) -> str:
        self.calls.append(history)
        self.system_prompts.append(system_prompt)
        return self.reply_text


class FakeWhatsApp:
    """Records outbound sends instead of hitting the Graph API."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    async def send_text(self, to: str, text: str) -> None:
        self.sent.append((to, text))


@pytest.fixture(autouse=True)
def _reset_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def fake_llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture
def fake_whatsapp() -> FakeWhatsApp:
    return FakeWhatsApp()


@pytest.fixture
def client(fake_llm: FakeLLM, fake_whatsapp: FakeWhatsApp):
    with TestClient(app) as test_client:
        # Override the real services wired by the lifespan with fakes.
        app.state.clinics = ClinicRegistry([SUNRISE, GREENFIELD])
        app.state.llm = fake_llm
        app.state.whatsapp = fake_whatsapp
        yield test_client


@pytest.fixture
def single_clinic_client(fake_llm: FakeLLM, fake_whatsapp: FakeWhatsApp):
    """Same app, but a registry with exactly one clinic (the degenerate case)."""
    with TestClient(app) as test_client:
        app.state.clinics = ClinicRegistry([SUNRISE])
        app.state.llm = fake_llm
        app.state.whatsapp = fake_whatsapp
        yield test_client
