# M1 — Multi-Tenant Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One FastAPI deployment serves many clinics: each clinic is a YAML file, the system prompt is rendered from it, and inbound WhatsApp messages are routed to the right clinic by `phone_number_id`.

**Architecture:** A `ClinicConfig` pydantic model is loaded from `clinics/*.yaml` into a `ClinicRegistry` at startup. The webhook reads `value.metadata.phone_number_id` from Meta's payload, resolves the clinic, renders that clinic's system prompt, keeps conversation history keyed by `(clinic_id, phone)`, and sends the reply through the clinic's own `phone_number_id` and token. A deployment with exactly one YAML file behaves exactly as today's single-tenant demo.

**Tech Stack:** Python 3.11+, FastAPI, pydantic v2, pydantic-settings, PyYAML (new), httpx, pytest + pytest-asyncio, ruff.

**Spec:** `docs/PRD.md` — section "F1 — Multi-tenant clinic registry" and milestone M1 in section 7. Read it first; this plan implements F1 and nothing from F2–F5.

## Global Constraints

- `pytest` and `ruff check .` must be green after every task. CI runs both (`.github/workflows/ci.yml`).
- `requires-python = ">=3.11"` (pyproject). Do not use syntax newer than 3.11.
- Ruff `line-length = 100` (pyproject). E501 is not enforced, but keep new code under 100 chars per line anyway.
- The behaviour rules in the prompt (tone, hard rules, booking flow, demo behaviours) stay **verbatim**. Only clinic facts move into the YAML. Do not reword the "reminder a day before" line (that is M2) and do not replace `0803 XXX XXXX` (that is M3).
- Unknown `phone_number_id` → log a warning and return HTTP 200. Never 4xx/5xx to Meta.
- Every conversation key is `(clinic_id, phone)`. Nothing is keyed by phone alone after Task 5.
- Degenerate case: a `clinics/` directory with one YAML file must pass the full suite and behave like the current demo.
- No new dependencies beyond `pyyaml`.
- Commit after every task with the message given in the task. Do not push to `base-setuo`.

## Setup before Task 1

Run from the repo root with the virtualenv active:

```bash
pip install -e ".[dev]"
pytest -q          # expect: 26 passed
ruff check .       # expect: All checks passed!
```

## File map

| Path | Responsibility |
|---|---|
| `src/app/models/clinic.py` (create) | `ClinicConfig`, `Doctor`, `Service` pydantic models. Pure data, no I/O. |
| `src/app/services/registry.py` (create) | `load_clinic_file`, `ClinicRegistry`, `ClinicConfigError`. YAML I/O and lookup by id / phone_number_id. |
| `clinics/sunrise-dental.yaml` (create) | The demo clinic's profile, moved out of `prompts.py`. |
| `src/app/prompts.py` (rewrite) | `render_system_prompt(clinic)`: fixed rules + rendered `CLINIC PROFILE`. Replaces the `SYSTEM_PROMPT` constant. |
| `src/app/models/whatsapp.py` (modify) | Add `Metadata` to `Value`; add `phone_number_id` to `IncomingMessage`. |
| `src/app/config.py` (modify) | Add `clinics_dir`; replace `whatsapp_phone_number_id` + `whatsapp_messages_url` with `messages_url_for(phone_number_id)`. |
| `src/app/services/conversation.py` (modify) | Key history by `(clinic_id, phone)`. |
| `src/app/services/llm.py` (modify) | `reply(history, system_prompt)`. |
| `src/app/services/whatsapp.py` (modify) | `send_text(clinic, to, text)` using the clinic's phone_number_id and token. |
| `src/app/routes/webhook.py` (modify) | Resolve clinic from metadata; pass clinic through the pipeline. |
| `src/app/main.py` (modify) | Load `ClinicRegistry` in lifespan; put it on `app.state.clinics`. |
| `tests/conftest.py` (modify) | Fakes take the new signatures; registry with two in-memory clinics; single-clinic fixture. |
| `tests/test_clinic_model.py`, `tests/test_registry.py` (create) | Unit tests for the two new modules. |
| Existing tests (modify) | Updated to the new signatures; prompt tests run against the rendered Sunrise prompt. |
| `README.md`, `.env.example`, `pyproject.toml` (modify) | Document the clinics directory and the new env var. |

---

### Task 1: `ClinicConfig` model

**Files:**
- Create: `src/app/models/clinic.py`
- Modify: `pyproject.toml` (add `pyyaml` dependency)
- Test: `tests/test_clinic_model.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `ClinicConfig`, `Doctor(name: str, role: str)`, `Service(name: str, price: str)`. All later tasks construct or read `ClinicConfig` with exactly the field names below.

- [ ] **Step 1: Add the PyYAML dependency**

In `pyproject.toml`, change the `dependencies` list to:

```toml
dependencies = [
    "fastapi>=0.111",
    "uvicorn[standard]>=0.30",
    "httpx>=0.27",
    "pydantic>=2.7",
    "pydantic-settings>=2.3",
    "openai>=1.30",
    "pyyaml>=6.0",
]
```

Run: `pip install -e ".[dev]"`
Expected: installs `PyYAML` without error.

- [ ] **Step 2: Write the failing tests**

Create `tests/test_clinic_model.py`:

```python
"""Tests for the per-clinic config model."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.clinic import ClinicConfig, Doctor, Service


def _valid_clinic_data() -> dict:
    return {
        "id": "test-clinic",
        "name": "Test Clinic",
        "short_name": "Test",
        "area": "Wuse 2, Abuja",
        "address": "1 Test Street, Wuse 2, Abuja",
        "phone": "0800 000 0000",
        "hours": "Mon–Fri 9:00am–5:00pm",
        "lead_doctor": "Dr. Test",
        "doctors": [{"name": "Dr. Test Person", "role": "Lead Dentist"}],
        "services": [{"name": "Consultation", "price": "10,000"}],
        "payment": "Cash, transfer, POS.",
        "hmos": ["Hygeia"],
        "cancellation_policy": "free up to 24h before.",
        "first_visit": "arrive 10 minutes early.",
        "phone_number_id": "111000000000000",
        "staff_phone": "2348000000000",
    }


def test_clinic_config_parses_valid_data() -> None:
    clinic = ClinicConfig.model_validate(_valid_clinic_data())

    assert clinic.id == "test-clinic"
    assert clinic.doctors == [Doctor(name="Dr. Test Person", role="Lead Dentist")]
    assert clinic.services == [Service(name="Consultation", price="10,000")]
    assert clinic.whatsapp_token is None
    assert clinic.address_note is None
    assert "coverage depends on their plan" in clinic.hmo_note


def test_clinic_config_rejects_unknown_fields() -> None:
    data = _valid_clinic_data()
    data["adress"] = "typo"

    with pytest.raises(ValidationError):
        ClinicConfig.model_validate(data)


@pytest.mark.parametrize("bad_id", ["Sunrise Dental", "sunrise_dental", "", "-sunrise"])
def test_clinic_config_rejects_invalid_id(bad_id: str) -> None:
    data = _valid_clinic_data()
    data["id"] = bad_id

    with pytest.raises(ValidationError):
        ClinicConfig.model_validate(data)


@pytest.mark.parametrize("field", ["doctors", "services"])
def test_clinic_config_requires_at_least_one_doctor_and_service(field: str) -> None:
    data = _valid_clinic_data()
    data[field] = []

    with pytest.raises(ValidationError):
        ClinicConfig.model_validate(data)


def test_clinic_config_accepts_optional_token_and_address_note() -> None:
    data = _valid_clinic_data()
    data["whatsapp_token"] = "clinic-token"
    data["address_note"] = "(opposite the market)"

    clinic = ClinicConfig.model_validate(data)

    assert clinic.whatsapp_token == "clinic-token"
    assert clinic.address_note == "(opposite the market)"
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `pytest tests/test_clinic_model.py -v`
Expected: FAIL at collection with `ModuleNotFoundError: No module named 'app.models.clinic'`.

- [ ] **Step 4: Write the model**

Create `src/app/models/clinic.py`:

```python
"""Per-clinic profile: everything the prompt renders and the webhook routes on.

Loaded from one YAML file per clinic (see app.services.registry). Unknown keys are
rejected so a typo in a config file fails at startup instead of silently
dropping a fact from the prompt.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Doctor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    role: str


class Service(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    price: str


class ClinicConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Identity
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    name: str
    short_name: str
    area: str
    address: str
    address_note: str | None = None
    phone: str
    hours: str

    # People and services
    lead_doctor: str
    doctors: list[Doctor] = Field(min_length=1)
    services: list[Service] = Field(min_length=1)

    # Policies
    payment: str
    hmos: list[str] = []
    hmo_note: str = (
        "Patient should bring HMO ID; coverage depends on their plan — "
        "for specific coverage questions, staff will confirm."
    )
    cancellation_policy: str
    first_visit: str

    # WhatsApp routing
    phone_number_id: str
    staff_phone: str
    whatsapp_token: str | None = None
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest tests/test_clinic_model.py -v`
Expected: 9 passed (5 functions, two of them parametrized).

- [ ] **Step 6: Lint and run the full suite**

Run: `ruff check . && pytest -q`
Expected: `All checks passed!` and `35 passed`.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml src/app/models/clinic.py tests/test_clinic_model.py
git commit -m "feat(m1): add ClinicConfig model and pyyaml dependency"
```

---

### Task 2: YAML loader and `ClinicRegistry`

**Files:**
- Create: `src/app/services/registry.py`
- Test: `tests/test_registry.py`

**Interfaces:**
- Consumes: `ClinicConfig` from Task 1.
- Produces:
  - `class ClinicConfigError(ValueError)`
  - `load_clinic_file(path: Path) -> ClinicConfig`
  - `class ClinicRegistry` with `__init__(self, clinics: Iterable[ClinicConfig])`, `from_directory(cls, directory: Path) -> ClinicRegistry`, `by_phone_number_id(self, phone_number_id: str | None) -> ClinicConfig | None`, `by_id(self, clinic_id: str) -> ClinicConfig | None`, `__len__`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_registry.py`:

```python
"""Tests for loading clinic YAML files and resolving clinics."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from app.models.clinic import ClinicConfig
from app.services.registry import ClinicConfigError, ClinicRegistry, load_clinic_file


def _write_clinic(directory: Path, clinic_id: str, phone_number_id: str) -> Path:
    path = directory / f"{clinic_id}.yaml"
    path.write_text(
        textwrap.dedent(
            f"""\
            id: {clinic_id}
            name: {clinic_id.title()} Clinic
            short_name: {clinic_id.title()}
            area: Wuse 2, Abuja
            address: 1 Test Street, Wuse 2, Abuja
            phone: "0800 000 0000"
            hours: "Mon–Fri 9:00am–5:00pm"
            lead_doctor: Dr. Test
            doctors:
              - name: Dr. Test Person
                role: Lead Dentist
            services:
              - name: Consultation
                price: "10,000"
            payment: Cash only.
            hmos: []
            cancellation_policy: free anytime.
            first_visit: bring a valid ID.
            phone_number_id: "{phone_number_id}"
            staff_phone: "2348000000000"
            """
        ),
        encoding="utf-8",
    )
    return path


def test_load_clinic_file_parses_yaml(tmp_path: Path) -> None:
    path = _write_clinic(tmp_path, "clinic-a", "111")

    clinic = load_clinic_file(path)

    assert isinstance(clinic, ClinicConfig)
    assert clinic.id == "clinic-a"
    assert clinic.phone_number_id == "111"
    assert clinic.services[0].price == "10,000"


def test_load_clinic_file_rejects_invalid_yaml(tmp_path: Path) -> None:
    path = tmp_path / "broken.yaml"
    path.write_text("id: [unclosed", encoding="utf-8")

    with pytest.raises(ClinicConfigError, match="invalid YAML"):
        load_clinic_file(path)


def test_load_clinic_file_rejects_non_mapping(tmp_path: Path) -> None:
    path = tmp_path / "list.yaml"
    path.write_text("- just\n- a list\n", encoding="utf-8")

    with pytest.raises(ClinicConfigError, match="mapping"):
        load_clinic_file(path)


def test_load_clinic_file_reports_validation_errors_with_path(tmp_path: Path) -> None:
    path = _write_clinic(tmp_path, "clinic-a", "111")
    path.write_text(path.read_text(encoding="utf-8") + "unknown_key: oops\n", encoding="utf-8")

    with pytest.raises(ClinicConfigError, match="clinic-a.yaml"):
        load_clinic_file(path)


def test_registry_from_directory_loads_every_yaml_file(tmp_path: Path) -> None:
    _write_clinic(tmp_path, "clinic-a", "111")
    _write_clinic(tmp_path, "clinic-b", "222")
    (tmp_path / "notes.txt").write_text("ignored", encoding="utf-8")

    registry = ClinicRegistry.from_directory(tmp_path)

    assert len(registry) == 2
    assert registry.by_id("clinic-a") is not None
    assert registry.by_id("clinic-b") is not None


def test_registry_resolves_by_phone_number_id(tmp_path: Path) -> None:
    _write_clinic(tmp_path, "clinic-a", "111")
    _write_clinic(tmp_path, "clinic-b", "222")
    registry = ClinicRegistry.from_directory(tmp_path)

    clinic = registry.by_phone_number_id("222")

    assert clinic is not None
    assert clinic.id == "clinic-b"


def test_registry_returns_none_for_unknown_or_missing_phone_number_id(tmp_path: Path) -> None:
    _write_clinic(tmp_path, "clinic-a", "111")
    registry = ClinicRegistry.from_directory(tmp_path)

    assert registry.by_phone_number_id("999") is None
    assert registry.by_phone_number_id(None) is None
    assert registry.by_id("nope") is None


def test_registry_rejects_duplicate_phone_number_id(tmp_path: Path) -> None:
    _write_clinic(tmp_path, "clinic-a", "111")
    _write_clinic(tmp_path, "clinic-b", "111")

    with pytest.raises(ClinicConfigError, match="duplicate phone_number_id"):
        ClinicRegistry.from_directory(tmp_path)


def test_registry_rejects_duplicate_clinic_id(tmp_path: Path) -> None:
    clinic = load_clinic_file(_write_clinic(tmp_path, "clinic-a", "111"))
    twin = clinic.model_copy(update={"phone_number_id": "222"})

    with pytest.raises(ClinicConfigError, match="duplicate clinic id"):
        ClinicRegistry([clinic, twin])


def test_registry_rejects_empty_directory(tmp_path: Path) -> None:
    with pytest.raises(ClinicConfigError, match="no clinic configs"):
        ClinicRegistry.from_directory(tmp_path)


def test_registry_rejects_missing_directory(tmp_path: Path) -> None:
    with pytest.raises(ClinicConfigError, match="not found"):
        ClinicRegistry.from_directory(tmp_path / "does-not-exist")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_registry.py -v`
Expected: FAIL at collection with `ModuleNotFoundError: No module named 'app.services.registry'`.

- [ ] **Step 3: Write the loader and registry**

Create `src/app/services/registry.py`:

```python
"""Clinic registry: loads per-clinic YAML files and resolves inbound routing.

One deployment serves many clinics. Meta delivers every phone number under one
app to the same webhook URL, so the registry maps the payload's
`phone_number_id` back to the clinic that owns it.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from pathlib import Path

import yaml
from pydantic import ValidationError

from app.models.clinic import ClinicConfig

logger = logging.getLogger(__name__)

_YAML_SUFFIXES = {".yaml", ".yml"}


class ClinicConfigError(ValueError):
    """A clinic config file is missing, malformed, or conflicts with another."""


def load_clinic_file(path: Path) -> ClinicConfig:
    """Parse one clinic YAML file into a ClinicConfig, naming the file in any error."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ClinicConfigError(f"{path}: invalid YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise ClinicConfigError(f"{path}: expected a mapping at the top level")
    try:
        return ClinicConfig.model_validate(raw)
    except ValidationError as exc:
        raise ClinicConfigError(f"{path}: {exc}") from exc


class ClinicRegistry:
    def __init__(self, clinics: Iterable[ClinicConfig]) -> None:
        self._by_id: dict[str, ClinicConfig] = {}
        self._by_phone_number_id: dict[str, ClinicConfig] = {}
        for clinic in clinics:
            if clinic.id in self._by_id:
                raise ClinicConfigError(f"duplicate clinic id: {clinic.id}")
            if clinic.phone_number_id in self._by_phone_number_id:
                raise ClinicConfigError(
                    f"duplicate phone_number_id: {clinic.phone_number_id}"
                )
            self._by_id[clinic.id] = clinic
            self._by_phone_number_id[clinic.phone_number_id] = clinic
        if not self._by_id:
            raise ClinicConfigError("no clinic configs loaded")

    @classmethod
    def from_directory(cls, directory: Path) -> ClinicRegistry:
        """Load every *.yaml / *.yml file in `directory` (sorted by name)."""
        if not directory.is_dir():
            raise ClinicConfigError(f"clinics directory not found: {directory}")
        paths = sorted(p for p in directory.iterdir() if p.suffix in _YAML_SUFFIXES)
        registry = cls(load_clinic_file(path) for path in paths)
        logger.info("Loaded %d clinic config(s) from %s", len(registry), directory)
        return registry

    def by_phone_number_id(self, phone_number_id: str | None) -> ClinicConfig | None:
        if phone_number_id is None:
            return None
        return self._by_phone_number_id.get(phone_number_id)

    def by_id(self, clinic_id: str) -> ClinicConfig | None:
        return self._by_id.get(clinic_id)

    def __len__(self) -> int:
        return len(self._by_id)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_registry.py -v`
Expected: 11 passed.

- [ ] **Step 5: Lint and run the full suite**

Run: `ruff check . && pytest -q`
Expected: `All checks passed!` and `46 passed`.

- [ ] **Step 6: Commit**

```bash
git add src/app/services/registry.py tests/test_registry.py
git commit -m "feat(m1): add clinic YAML loader and ClinicRegistry"
```

---

### Task 3: Read `phone_number_id` from the webhook payload

**Files:**
- Modify: `src/app/models/whatsapp.py`
- Test: `tests/test_whatsapp_models.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `Value.metadata: Metadata | None`; `IncomingMessage.phone_number_id: str | None`. Task 4's route reads `message.phone_number_id`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_whatsapp_models.py`:

```python
def test_first_text_message_carries_phone_number_id_from_metadata() -> None:
    payload = WebhookPayload.model_validate(
        {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "2349000000000",
                                    "phone_number_id": "123456789012345",
                                },
                                "messages": [
                                    {
                                        "from": "2348012345678",
                                        "id": "wamid.123",
                                        "type": "text",
                                        "text": {"body": "Hello"},
                                    }
                                ],
                            }
                        }
                    ]
                }
            ],
        }
    )

    message = payload.first_text_message()

    assert message is not None
    assert message.phone_number_id == "123456789012345"


def test_first_text_message_phone_number_id_is_none_without_metadata() -> None:
    payload = WebhookPayload.model_validate(
        {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "from": "2348012345678",
                                        "id": "wamid.123",
                                        "type": "text",
                                        "text": {"body": "Hello"},
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        }
    )

    message = payload.first_text_message()

    assert message is not None
    assert message.phone_number_id is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_whatsapp_models.py -v`
Expected: the two new tests FAIL with `AttributeError: 'IncomingMessage' object has no attribute 'phone_number_id'`.

- [ ] **Step 3: Add the metadata model and field**

In `src/app/models/whatsapp.py`, replace the `Value` class and the `first_text_message` / `IncomingMessage` definitions so the file reads:

```python
class Metadata(_Lenient):
    """The business phone number the message was sent to."""

    display_phone_number: str | None = None
    phone_number_id: str | None = None


class Value(_Lenient):
    messaging_product: str | None = None
    metadata: Metadata | None = None
    messages: list[Message] = []


class Change(_Lenient):
    value: Value
    field: str | None = None


class Entry(_Lenient):
    id: str | None = None
    changes: list[Change] = []


class WebhookPayload(_Lenient):
    object: str | None = None
    entry: list[Entry] = []

    def first_text_message(self) -> IncomingMessage | None:
        """Return the first inbound text message, normalized, if present."""
        for entry in self.entry:
            for change in entry.changes:
                metadata = change.value.metadata
                phone_number_id = metadata.phone_number_id if metadata else None
                for message in change.value.messages:
                    if message.type == "text" and message.text is not None:
                        return IncomingMessage(
                            from_number=message.from_,
                            message_id=message.id,
                            text=message.text.body,
                            phone_number_id=phone_number_id,
                        )
        return None


class IncomingMessage(BaseModel):
    """Normalized inbound text message."""

    from_number: str
    message_id: str
    text: str
    phone_number_id: str | None = None
```

Leave `_Lenient`, `TextBody`, and `Message` exactly as they are.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_whatsapp_models.py -v`
Expected: 6 passed.

- [ ] **Step 5: Lint and run the full suite**

Run: `ruff check . && pytest -q`
Expected: `All checks passed!` and `48 passed`.

- [ ] **Step 6: Commit**

```bash
git add src/app/models/whatsapp.py tests/test_whatsapp_models.py
git commit -m "feat(m1): parse metadata.phone_number_id from webhook payload"
```

---

### Task 4: Sunrise YAML, registry in lifespan, route resolves the clinic

After this task the app loads `clinics/` at startup and drops messages for unknown numbers. Services still use their old signatures; that changes in Tasks 5–7.

**Files:**
- Create: `clinics/sunrise-dental.yaml`
- Modify: `src/app/config.py`
- Modify: `src/app/main.py`
- Modify: `src/app/routes/webhook.py`
- Modify: `tests/conftest.py`
- Test: `tests/test_webhook.py`

**Interfaces:**
- Consumes: `ClinicRegistry.from_directory`, `ClinicRegistry.by_phone_number_id`, `IncomingMessage.phone_number_id`.
- Produces: `Settings.clinics_dir: str`; `app.state.clinics: ClinicRegistry`; conftest constants `SUNRISE`, `SUNRISE_PHONE_NUMBER_ID`, `GREENFIELD`; `_inbound_payload(from_number, text, phone_number_id=SUNRISE_PHONE_NUMBER_ID)` in `tests/test_webhook.py`.

- [ ] **Step 1: Create the demo clinic YAML**

Create `clinics/sunrise-dental.yaml`. Every value is copied verbatim from the `CLINIC PROFILE` block in `src/app/prompts.py`; do not "improve" any wording.

```yaml
# Demo clinic. Facts here are rendered into the CLINIC PROFILE block of the
# system prompt (see src/app/prompts.py). Fictional clinic, placeholder phone.
id: sunrise-dental
name: "Sunrise Dental & Family Clinic"
short_name: "Sunrise Dental"
area: "Wuse 2, Abuja"
address: "14 Aminu Kano Crescent, Wuse 2, Abuja"
address_note: "(opposite Sherif Plaza). Parking available."
phone: "0803 XXX XXXX"
hours: "Mon–Fri 8:00am–6:00pm · Sat 9:00am–4:00pm · Sun closed (emergencies: call line)"
lead_doctor: "Dr. Adaeze"
doctors:
  - name: "Dr. Adaeze Okonkwo"
    role: "Lead Dentist"
  - name: "Dr. Ibrahim Bello"
    role: "Family Dentistry"
  - name: "Dr. Funke Alabi"
    role: "Orthodontics, Tue & Thu only"
services:
  - name: "Consultation / Checkup"
    price: "10,000 (waived if treatment is done same visit)"
  - name: "Scaling & Polishing (cleaning)"
    price: "25,000"
  - name: "Teeth Whitening"
    price: "80,000"
  - name: "Tooth Extraction (simple)"
    price: "20,000–35,000 depending on assessment"
  - name: "Fillings (composite)"
    price: "25,000–40,000 per tooth"
  - name: "Root Canal Treatment"
    price: "90,000–120,000 per tooth (requires consultation first)"
  - name: "Braces / Orthodontics"
    price: "from 450,000 (free consultation with Dr. Funke, Tue/Thu)"
  - name: "Dentures"
    price: "from 70,000 (assessment required)"
  - name: "Children's Dentistry"
    price: "consultation 8,000"
  - name: "X-ray (digital)"
    price: "7,000"
payment: "Cash, transfer, POS. Payment plans available for treatments above ₦100,000 (50% upfront)."
hmos:
  - "Hygeia"
  - "AXA Mansard"
  - "Reliance HMO"
  - "Leadway Health"
cancellation_policy: "free up to 24h before; same-day cancellations may forfeit the consultation deposit for specialist appointments."
first_visit: "arrive 10 minutes early with a valid ID; HMO patients bring their card."

# WhatsApp routing. phone_number_id is Meta's numeric id for this clinic's
# number (from the WhatsApp Manager). Replace before going live.
phone_number_id: "123456789012345"
staff_phone: "2348000000000"
# whatsapp_token: ""   # optional; defaults to WHATSAPP_TOKEN from the environment
```

Verify it loads:

```bash
python -c "from pathlib import Path; from app.services.registry import load_clinic_file; c = load_clinic_file(Path('clinics/sunrise-dental.yaml')); print(c.id, len(c.services))"
```

Expected output: `sunrise-dental 10`.

- [ ] **Step 2: Add `clinics_dir` to settings**

In `src/app/config.py`, add one field after `whatsapp_api_version`:

```python
    # Clinics: directory of per-clinic YAML files (one file per clinic)
    clinics_dir: str = "clinics"
```

Leave `whatsapp_phone_number_id` and `whatsapp_messages_url` in place for now; Task 7 removes them.

- [ ] **Step 3: Write the failing tests**

In `tests/conftest.py`, add these imports and constants after `VERIFY_TOKEN = "test-verify-token"`:

```python
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
```

Then change the `client` fixture to install the two-clinic registry, and add a single-clinic fixture:

```python
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
```

In `tests/test_webhook.py`, change the imports and payload helper:

```python
from typing import Any

import pytest

from app.main import app
from conftest import GREENFIELD_PHONE_NUMBER_ID, SUNRISE_PHONE_NUMBER_ID

VERIFY_TOKEN = "test-verify-token"


def _inbound_payload(
    from_number: str,
    text: str,
    phone_number_id: str = SUNRISE_PHONE_NUMBER_ID,
) -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "entry-1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "2349000000000",
                                "phone_number_id": phone_number_id,
                            },
                            "messages": [
                                {
                                    "from": from_number,
                                    "id": "wamid.123",
                                    "type": "text",
                                    "text": {"body": text},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
```

`from conftest import ...` works because pytest adds `tests/` to `sys.path` (rootdir conftest, no `__init__.py`). Do not add `tests/__init__.py`.

Also in `test_webhook_processes_first_text_across_entries`, add a `metadata` block to the **second** entry's `value` so the text message has a routable number:

```python
                        "value": {
                            "metadata": {"phone_number_id": SUNRISE_PHONE_NUMBER_ID},
                            "messages": [
                                {
                                    "from": "2348012345678",
                                    "id": "wamid.text",
                                    "type": "text",
                                    "text": {"body": "Book cleaning"},
                                }
                            ]
                        }
```

Append these new tests to `tests/test_webhook.py`:

```python
def test_lifespan_loads_clinics_from_clinics_dir():
    with TestClient(app):
        registry = app.state.clinics

    assert registry.by_id("sunrise-dental") is not None
    assert registry.by_phone_number_id(SUNRISE_PHONE_NUMBER_ID) is not None


def test_unknown_phone_number_id_is_logged_and_ignored(
    client, fake_llm: Any, fake_whatsapp: Any, caplog: pytest.LogCaptureFixture
):
    with caplog.at_level("WARNING", logger="app.routes.webhook"):
        resp = client.post(
            "/webhook",
            json=_inbound_payload("2348012345678", "Hello", phone_number_id="999"),
        )

    assert resp.status_code == 200
    assert fake_llm.calls == []
    assert fake_whatsapp.sent == []
    assert "No clinic registered for phone_number_id='999'" in caplog.text


def test_text_without_metadata_is_ignored(client, fake_llm: Any, fake_whatsapp: Any):
    payload = _inbound_payload("2348012345678", "Hello")
    del payload["entry"][0]["changes"][0]["value"]["metadata"]

    resp = client.post("/webhook", json=payload)

    assert resp.status_code == 200
    assert fake_llm.calls == []
    assert fake_whatsapp.sent == []


def test_message_to_second_clinic_number_is_processed(client, fake_llm: Any, fake_whatsapp: Any):
    resp = client.post(
        "/webhook",
        json=_inbound_payload("2348012345678", "Hello", phone_number_id=GREENFIELD_PHONE_NUMBER_ID),
    )

    assert resp.status_code == 200
    assert len(fake_llm.calls) == 1
    assert len(fake_whatsapp.sent) == 1
```

Add `from fastapi.testclient import TestClient` to the imports at the top of `tests/test_webhook.py`.

- [ ] **Step 4: Run the tests to verify they fail**

Run: `pytest tests/test_webhook.py -v`
Expected: `test_lifespan_loads_clinics_from_clinics_dir` FAILS with `AttributeError: 'State' object has no attribute 'clinics'`; `test_unknown_phone_number_id_is_logged_and_ignored` and `test_text_without_metadata_is_ignored` FAIL because the fake LLM was called. The pre-existing tests still pass.

- [ ] **Step 5: Load the registry in the lifespan**

Rewrite `src/app/main.py`:

```python
"""FastAPI entrypoint: wires settings and services, registers the webhook routes."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

import httpx
from fastapi import FastAPI

from app.config import get_settings
from app.routes.webhook import router as webhook_router
from app.services.conversation import ConversationStore
from app.services.llm import LLMClient
from app.services.registry import ClinicRegistry
from app.services.whatsapp import WhatsAppClient


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    http = httpx.AsyncClient(timeout=30.0)

    app.state.settings = settings
    # Fails loudly at startup if the directory is missing, empty, or has a bad file.
    app.state.clinics = ClinicRegistry.from_directory(Path(settings.clinics_dir))
    app.state.conversations = ConversationStore(max_turns=settings.max_history_turns)
    app.state.llm = LLMClient(settings)
    app.state.whatsapp = WhatsAppClient(settings, http)

    try:
        yield
    finally:
        await http.aclose()


app = FastAPI(title="Clinic Front Desk (WhatsApp)", lifespan=lifespan)
app.include_router(webhook_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 6: Resolve the clinic in the route**

In `src/app/routes/webhook.py`, replace the body of `receive_webhook` from `message = payload.first_text_message()` to the end with:

```python
    message = payload.first_text_message()
    if message is None:
        return Response(status_code=200)

    state = request.app.state
    clinic = state.clinics.by_phone_number_id(message.phone_number_id)
    if clinic is None:
        logger.warning(
            "No clinic registered for phone_number_id=%r; ignoring message",
            message.phone_number_id,
        )
        return Response(status_code=200)

    phone = message.from_number

    try:
        state.conversations.add_user(phone, message.text)
        reply = await state.llm.reply(state.conversations.get(phone))
        state.conversations.add_assistant(phone, reply)
        await state.whatsapp.send_text(phone, reply)
    except Exception:
        logger.exception("Failed to process WhatsApp webhook message for clinic %s", clinic.id)

    return Response(status_code=200)
```

Update the docstring's second line to: `Always returns 200 so Meta does not retry; non-text events and unknown numbers are ignored.`

- [ ] **Step 7: Run the tests to verify they pass**

Run: `pytest tests/test_webhook.py -v`
Expected: 13 passed.

- [ ] **Step 8: Lint and run the full suite**

Run: `ruff check . && pytest -q`
Expected: `All checks passed!` and `52 passed`.

- [ ] **Step 9: Commit**

```bash
git add clinics/sunrise-dental.yaml src/app/config.py src/app/main.py src/app/routes/webhook.py tests/conftest.py tests/test_webhook.py
git commit -m "feat(m1): load clinic registry at startup and route inbound by phone_number_id"
```

---

### Task 5: Conversation history keyed by `(clinic_id, phone)`

**Files:**
- Modify: `src/app/services/conversation.py`
- Modify: `src/app/routes/webhook.py`
- Test: `tests/test_conversation.py`, `tests/test_webhook.py`

**Interfaces:**
- Consumes: `clinic.id` from the resolved `ClinicConfig`.
- Produces: `ConversationStore.get(clinic_id: str, phone: str)`, `add_user(clinic_id, phone, text)`, `add_assistant(clinic_id, phone, text)`.

- [ ] **Step 1: Rewrite the unit tests**

Replace the whole of `tests/test_conversation.py` with:

```python
"""Tests for in-memory conversation history behavior."""

from __future__ import annotations

from app.services.conversation import ConversationStore


def test_conversation_store_keeps_histories_isolated_per_phone() -> None:
    store = ConversationStore(max_turns=10)

    store.add_user("clinic-a", "2348011111111", "Hello")
    store.add_user("clinic-a", "2348022222222", "Hi")
    store.add_assistant("clinic-a", "2348011111111", "Good morning")

    assert store.get("clinic-a", "2348011111111") == [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Good morning"},
    ]
    assert store.get("clinic-a", "2348022222222") == [{"role": "user", "content": "Hi"}]


def test_conversation_store_keeps_histories_isolated_per_clinic() -> None:
    store = ConversationStore(max_turns=10)

    store.add_user("clinic-a", "2348012345678", "Price of a filling?")
    store.add_user("clinic-b", "2348012345678", "Do you do malaria tests?")

    assert store.get("clinic-a", "2348012345678") == [
        {"role": "user", "content": "Price of a filling?"}
    ]
    assert store.get("clinic-b", "2348012345678") == [
        {"role": "user", "content": "Do you do malaria tests?"}
    ]


def test_conversation_store_returns_copy_of_history() -> None:
    store = ConversationStore(max_turns=10)
    store.add_user("clinic-a", "2348012345678", "Hello")

    history = store.get("clinic-a", "2348012345678")
    history.append({"role": "assistant", "content": "Mutated outside"})

    assert store.get("clinic-a", "2348012345678") == [{"role": "user", "content": "Hello"}]


def test_conversation_store_trims_to_max_turns() -> None:
    store = ConversationStore(max_turns=2)

    store.add_user("clinic-a", "2348012345678", "First")
    store.add_assistant("clinic-a", "2348012345678", "Reply")
    store.add_user("clinic-a", "2348012345678", "Second")

    assert store.get("clinic-a", "2348012345678") == [
        {"role": "assistant", "content": "Reply"},
        {"role": "user", "content": "Second"},
    ]
```

Append to `tests/test_webhook.py`:

```python
def test_conversations_are_isolated_per_clinic(client, fake_llm: Any):
    client.post("/webhook", json=_inbound_payload("2348000000000", "Hello Sunrise"))
    client.post(
        "/webhook",
        json=_inbound_payload(
            "2348000000000", "Hello Greenfield", phone_number_id=GREENFIELD_PHONE_NUMBER_ID
        ),
    )

    # Same patient phone, different clinic: the second history starts fresh.
    assert [m["content"] for m in fake_llm.calls[1]] == ["Hello Greenfield"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_conversation.py tests/test_webhook.py::test_conversations_are_isolated_per_clinic -v`
Expected: conversation tests FAIL with `TypeError: ... takes 3 positional arguments but 4 were given`; the webhook test FAILS because the second history contains both messages.

- [ ] **Step 3: Rewrite the store**

Replace the whole of `src/app/services/conversation.py` with:

```python
"""In-memory per-conversation history.

Keyed by (clinic_id, patient phone) so the same patient talking to two clinics
gets two independent threads. History is trimmed to the most recent
`max_turns` messages (a turn = one user or one assistant message). This is
intentionally non-persistent — it resets on restart. Single-process only.
"""

from __future__ import annotations

from collections import defaultdict

ConversationKey = tuple[str, str]


class ConversationStore:
    def __init__(self, max_turns: int) -> None:
        self._max_turns = max_turns
        self._history: dict[ConversationKey, list[dict[str, str]]] = defaultdict(list)

    def get(self, clinic_id: str, phone: str) -> list[dict[str, str]]:
        return list(self._history[(clinic_id, phone)])

    def add_user(self, clinic_id: str, phone: str, text: str) -> None:
        self._append((clinic_id, phone), "user", text)

    def add_assistant(self, clinic_id: str, phone: str, text: str) -> None:
        self._append((clinic_id, phone), "assistant", text)

    def _append(self, key: ConversationKey, role: str, content: str) -> None:
        history = self._history[key]
        history.append({"role": role, "content": content})
        if len(history) > self._max_turns:
            del history[: len(history) - self._max_turns]
```

- [ ] **Step 4: Update the route**

In `src/app/routes/webhook.py`, change the three store calls inside the `try` block:

```python
    try:
        state.conversations.add_user(clinic.id, phone, message.text)
        reply = await state.llm.reply(state.conversations.get(clinic.id, phone))
        state.conversations.add_assistant(clinic.id, phone, reply)
        await state.whatsapp.send_text(phone, reply)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest tests/test_conversation.py tests/test_webhook.py -v`
Expected: 4 + 14 = 18 passed.

- [ ] **Step 6: Lint and run the full suite**

Run: `ruff check . && pytest -q`
Expected: `All checks passed!` and `54 passed`.

- [ ] **Step 7: Commit**

```bash
git add src/app/services/conversation.py src/app/routes/webhook.py tests/test_conversation.py tests/test_webhook.py
git commit -m "feat(m1): key conversation history by (clinic_id, phone)"
```

---

### Task 6: Prompt template rendered per clinic

This task removes the `SYSTEM_PROMPT` constant. `LLMClient.reply` gains a `system_prompt` argument and the route renders it from the resolved clinic, all in one commit so the real path never references a missing constant.

**Files:**
- Rewrite: `src/app/prompts.py`
- Modify: `src/app/services/llm.py`
- Modify: `src/app/routes/webhook.py`
- Modify: `tests/conftest.py` (FakeLLM signature)
- Test: `tests/test_prompts.py`, `tests/test_llm_service.py`, `tests/test_webhook.py`

**Interfaces:**
- Consumes: `ClinicConfig` fields from Task 1.
- Produces: `render_system_prompt(clinic: ClinicConfig) -> str`; `LLMClient.reply(history: list[dict[str, str]], system_prompt: str) -> str`; `FakeLLM.system_prompts: list[str]`.

- [ ] **Step 1: Rewrite the prompt tests**

Replace the whole of `tests/test_prompts.py` with:

```python
"""Tests for demo-critical prompt facts, safety rules, and per-clinic rendering."""

from __future__ import annotations

from app.prompts import render_system_prompt
from conftest import GREENFIELD, SUNRISE

SUNRISE_PROMPT = render_system_prompt(SUNRISE)
GREENFIELD_PROMPT = render_system_prompt(GREENFIELD)


def test_prompt_contains_clinic_identity_and_location() -> None:
    assert "virtual front desk assistant for Sunrise Dental & Family Clinic, Wuse 2, Abuja" in (
        SUNRISE_PROMPT
    )
    assert "CLINIC PROFILE — Sunrise Dental & Family Clinic" in SUNRISE_PROMPT
    assert (
        "Location: 14 Aminu Kano Crescent, Wuse 2, Abuja (opposite Sherif Plaza). "
        "Parking available." in SUNRISE_PROMPT
    )
    assert "📍 Sunrise Dental & Family Clinic, 14 Aminu Kano Crescent, Wuse 2, Abuja" in (
        SUNRISE_PROMPT
    )


def test_prompt_contains_demo_critical_prices_and_hmo_list() -> None:
    assert "Root Canal Treatment — 90,000–120,000 per tooth (requires consultation first)" in (
        SUNRISE_PROMPT
    )
    assert "Scaling & Polishing (cleaning) — 25,000" in SUNRISE_PROMPT
    assert "Braces / Orthodontics — from 450,000" in SUNRISE_PROMPT
    assert "HMOs accepted: Hygeia, AXA Mansard, Reliance HMO, Leadway Health." in SUNRISE_PROMPT
    assert "coverage depends on their plan" in SUNRISE_PROMPT


def test_prompt_lists_every_service_and_doctor_from_config() -> None:
    for service in SUNRISE.services:
        assert f"{service.name} — {service.price}" in SUNRISE_PROMPT
    assert (
        "Doctors: Dr. Adaeze Okonkwo (Lead Dentist), Dr. Ibrahim Bello (Family Dentistry), "
        "Dr. Funke Alabi (Orthodontics, Tue & Thu only)" in SUNRISE_PROMPT
    )
    assert (
        "Hours: Mon–Fri 8:00am–6:00pm · Sat 9:00am–4:00pm · Sun closed (emergencies: call line)"
        in SUNRISE_PROMPT
    )


def test_prompt_contains_safety_and_handoff_rules() -> None:
    assert "Never give medical advice" in SUNRISE_PROMPT
    assert "No diagnosis, no treatment suggestions" in SUNRISE_PROMPT
    assert "but Dr. Adaeze can see you — we have openings today" in SUNRISE_PROMPT
    assert "This sounds urgent. Please call us right now on 0803 XXX XXXX" in SUNRISE_PROMPT
    assert "I'll connect you with our front desk team — they'll reply here shortly." in (
        SUNRISE_PROMPT
    )
    assert "never ask for or record medical history" in SUNRISE_PROMPT


def test_prompt_contains_booking_confirmation_markers() -> None:
    assert "✅ *Appointment confirmed*" in SUNRISE_PROMPT
    assert "👤 [Name]" in SUNRISE_PROMPT
    assert "🦷 [Service]" in SUNRISE_PROMPT
    assert "📅 [Day, Date — Time]" in SUNRISE_PROMPT
    assert "You'll receive a reminder a day before. Reply RESCHEDULE or CANCEL anytime." in (
        SUNRISE_PROMPT
    )


def test_prompt_contains_bot_disclosure() -> None:
    assert "Yes — I'm Sunrise Dental's virtual assistant." in SUNRISE_PROMPT
    assert "book appointments 24/7" in SUNRISE_PROMPT
    assert "Thank you for reaching out to Sunrise Dental" in SUNRISE_PROMPT


def test_prompt_renders_other_clinic_facts_and_never_leaks_sunrise() -> None:
    assert "Greenfield Medical Centre, Lekki Phase 1, Lagos" in GREENFIELD_PROMPT
    assert "Malaria Test — 5,000" in GREENFIELD_PROMPT
    assert "Doctors: Dr. Tunde Bakare (Medical Director)" in GREENFIELD_PROMPT
    assert "HMOs accepted: Avon HMO." in GREENFIELD_PROMPT
    assert "but Dr. Tunde can see you" in GREENFIELD_PROMPT
    assert "Please call us right now on 0701 000 0000" in GREENFIELD_PROMPT
    assert "Yes — I'm Greenfield's virtual assistant." in GREENFIELD_PROMPT
    assert "Location: 5 Admiralty Way, Lekki Phase 1, Lagos\n" in GREENFIELD_PROMPT

    assert "Sunrise" not in GREENFIELD_PROMPT
    assert "Aminu Kano" not in GREENFIELD_PROMPT
    assert "Adaeze" not in GREENFIELD_PROMPT


def test_prompt_behaviour_rules_are_identical_across_clinics() -> None:
    def rules_section(prompt: str) -> str:
        return prompt.split("Tone & style", 1)[1].split("Hard rules", 1)[0]

    assert rules_section(SUNRISE_PROMPT).replace("Sunrise Dental", "X") == rules_section(
        GREENFIELD_PROMPT
    ).replace("Greenfield", "X")


def test_prompt_renders_none_when_clinic_has_no_hmos() -> None:
    clinic = GREENFIELD.model_copy(update={"hmos": []})

    assert "HMOs accepted: None." in render_system_prompt(clinic)
```

- [ ] **Step 2: Update the LLM service tests**

In `tests/test_llm_service.py`:

Remove the line `from app.prompts import SYSTEM_PROMPT`.

Replace `test_reply_sends_system_prompt_plus_conversation_history` with:

```python
@pytest.mark.asyncio
async def test_reply_sends_given_system_prompt_plus_conversation_history() -> None:
    client = LLMClient(_settings())
    history = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Good morning"},
    ]

    await client.reply(history, "You are the front desk for Clinic X.")

    fake_openai = FakeAsyncOpenAI.instances[0]
    assert fake_openai.api_key == "test-key"
    assert fake_openai.base_url is None
    assert fake_openai.calls == [
        {
            "model": "demo-model",
            "messages": [
                {"role": "system", "content": "You are the front desk for Clinic X."},
                *history,
            ],
            "temperature": 0.4,
        }
    ]
```

In the remaining two tests change `await client.reply([{"role": "user", "content": "Hello"}])` to `await client.reply([{"role": "user", "content": "Hello"}], "system")`.

- [ ] **Step 3: Update the fake and the webhook assertions**

In `tests/conftest.py`, replace `FakeLLM` with:

```python
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
```

Append to `tests/test_webhook.py`:

```python
def test_reply_uses_the_receiving_clinics_prompt(client, fake_llm: Any):
    client.post("/webhook", json=_inbound_payload("2348012345678", "How much is a root canal?"))
    client.post(
        "/webhook",
        json=_inbound_payload(
            "2348012345678", "Do you do malaria tests?", phone_number_id=GREENFIELD_PHONE_NUMBER_ID
        ),
    )

    sunrise_prompt, greenfield_prompt = fake_llm.system_prompts
    assert "Root Canal Treatment — 90,000–120,000" in sunrise_prompt
    assert "Malaria Test" not in sunrise_prompt
    assert "Malaria Test — 5,000" in greenfield_prompt
    assert "Root Canal" not in greenfield_prompt
```

- [ ] **Step 4: Run the tests to verify they fail**

Run: `pytest tests/test_prompts.py tests/test_llm_service.py tests/test_webhook.py -v`
Expected: `test_prompts.py` FAILS at collection with `ImportError: cannot import name 'render_system_prompt'`; the LLM tests FAIL with `TypeError: reply() takes 2 positional arguments but 3 were given`; `test_reply_uses_the_receiving_clinics_prompt` FAILS with `TypeError` from the fake.

- [ ] **Step 5: Rewrite `prompts.py` as a template**

Replace the whole of `src/app/prompts.py` with the following. The rule text is the existing prompt verbatim with clinic facts replaced by fields; compare against `git show HEAD:src/app/prompts.py` while editing and keep every rule sentence unchanged.

```python
"""Single source of truth for the assistant's behavior.

The behavior rules (tone, hard rules, booking flow, demo behaviors) are fixed for
every clinic. The CLINIC PROFILE block, and the handful of clinic names that
appear inside the rules, are rendered from a ClinicConfig. Edit this file to
retune behavior; edit the clinic's YAML to change facts.
"""

from __future__ import annotations

from app.models.clinic import ClinicConfig


def render_system_prompt(clinic: ClinicConfig) -> str:
    """Render the complete system prompt for one clinic."""
    location = clinic.address
    if clinic.address_note:
        location = f"{clinic.address} {clinic.address_note}"
    doctors = ", ".join(f"{d.name} ({d.role})" for d in clinic.doctors)
    services = "\n".join(f"{s.name} — {s.price}" for s in clinic.services)
    hmos = ", ".join(clinic.hmos) if clinic.hmos else "None"

    return f"""\
You are the virtual front desk assistant for {clinic.name}, {clinic.area}. You answer the clinic's WhatsApp messages. Your job: answer questions about the clinic accurately, and book, reschedule, or cancel appointments. Nothing else.

Tone & style
Warm, professional, respectful — Nigerian business courtesy ("Good morning, ma", "Thank you for reaching out to {clinic.short_name}").
WhatsApp style: short messages, 1–3 sentences. Never send long paragraphs. Use at most one emoji per message, and only friendly ones (🙂, 🦷, ✅).
Mirror the patient's language register. If they write Pidgin, you may respond warmly in simple English with a friendly tone — do not imitate Pidgin awkwardly.
Always answer instantly and directly. No filler like "Great question!"

Hard rules (never break these)
Never give medical advice. No diagnosis, no treatment suggestions, no "it might be...". If asked anything clinical ("my tooth hurts, what should I take?"), respond with care and pivot to booking: "I'm sorry you're in pain. I can't advise on treatment, but {clinic.lead_doctor} can see you — we have openings today. Shall I book you in?"
Never invent information. If something is not in the clinic profile below, say: "Let me have one of our staff confirm that for you — they'll reply shortly." Never guess prices, never make up services.
Emergencies: if a patient describes severe bleeding, trauma, swelling affecting breathing, or anything alarming, immediately say: "This sounds urgent. Please call us right now on {clinic.phone} or go to the nearest emergency room. We will prioritize you."
Human handoff: if the patient asks for a human, is upset, or you cannot resolve something in 2 attempts, say: "I'll connect you with our front desk team — they'll reply here shortly." Then stop responding in that thread.
Privacy: never ask for or record medical history, test results, or sensitive details. Appointment reason in 2–3 words maximum ("tooth cleaning", "checkup").

Booking flow
Collect, in natural conversation (not a form): (1) full name, (2) service needed, (3) preferred day and time, (4) new patient or returning.
Offer 2 specific alternative slots if their preference is unavailable (vary these realistically; clinic hours below).
Confirm with this exact format:

> ✅ *Appointment confirmed*
> 👤 [Name]
> 🦷 [Service]
> 📅 [Day, Date — Time]
> 📍 {clinic.name}, {clinic.address}
> You'll receive a reminder a day before. Reply RESCHEDULE or CANCEL anytime.

Rescheduling/cancelling: confirm identity by name, confirm the change politely, no penalties mentioned unless asked (cancellation policy below).

CLINIC PROFILE — {clinic.name}

Location: {location}
Phone: {clinic.phone}
Hours: {clinic.hours}
Doctors: {doctors}

Services & prices (₦):
{services}

Payment: {clinic.payment}
HMOs accepted: {hmos}. {clinic.hmo_note}
Cancellation policy: {clinic.cancellation_policy}
First visit: {clinic.first_visit}

Demo behavior notes
If asked "are you a bot/AI?" answer honestly: "Yes — I'm {clinic.short_name}'s virtual assistant. I can answer questions and book appointments 24/7, and our staff are always available if you need them."
Handle price haggling gracefully: prices are fixed, but mention the payment plan and the waived consultation fee.
If asked something playful or off-topic, give one short friendly response and steer back to the clinic.
"""
```

Note: the confirmation card's `📍` line now renders `{clinic.name}, {clinic.address}`, which for Sunrise ends in `Wuse 2, Abuja` instead of the old `Wuse 2`. That is the one intentional text difference and the prompt test above asserts the new form.

- [ ] **Step 6: Make `LLMClient.reply` take the prompt**

Replace the whole of `src/app/services/llm.py` with:

```python
"""Async LLM client: turns a system prompt plus conversation history into a reply."""

from __future__ import annotations

from openai import AsyncOpenAI

from app.config import Settings


class LLMClient:
    def __init__(self, settings: Settings) -> None:
        self._model = settings.llm_model
        self._client = AsyncOpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url or None,
        )

    async def reply(self, history: list[dict[str, str]], system_prompt: str) -> str:
        """Generate the assistant reply for the given clinic prompt and history."""
        messages = [{"role": "system", "content": system_prompt}, *history]
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,  # type: ignore[arg-type]
            temperature=0.4,
        )
        content = response.choices[0].message.content
        return (content or "").strip()
```

- [ ] **Step 7: Render the prompt in the route**

In `src/app/routes/webhook.py`, add the import `from app.prompts import render_system_prompt` after `from app.models.whatsapp import WebhookPayload`, and change the `try` block to:

```python
    try:
        state.conversations.add_user(clinic.id, phone, message.text)
        history = state.conversations.get(clinic.id, phone)
        reply = await state.llm.reply(history, render_system_prompt(clinic))
        state.conversations.add_assistant(clinic.id, phone, reply)
        await state.whatsapp.send_text(phone, reply)
```

- [ ] **Step 8: Run the tests to verify they pass**

Run: `pytest tests/test_prompts.py tests/test_llm_service.py tests/test_webhook.py -v`
Expected: 9 + 3 + 15 = 27 passed.

- [ ] **Step 9: Lint and run the full suite**

Run: `ruff check . && pytest -q`
Expected: `All checks passed!` and `59 passed`. Also confirm nothing still imports the old constant:

```bash
grep -rn "SYSTEM_PROMPT" src tests
```

Expected: no output.

- [ ] **Step 10: Commit**

```bash
git add src/app/prompts.py src/app/services/llm.py src/app/routes/webhook.py tests/conftest.py tests/test_prompts.py tests/test_llm_service.py tests/test_webhook.py
git commit -m "feat(m1): render system prompt per clinic from ClinicConfig"
```

---

### Task 7: Outbound sends use the clinic's number and token

**Files:**
- Modify: `src/app/config.py`
- Modify: `src/app/services/whatsapp.py`
- Modify: `src/app/routes/webhook.py`
- Modify: `tests/conftest.py` (FakeWhatsApp)
- Modify: `.env.example`
- Test: `tests/test_whatsapp_service.py`, `tests/test_webhook.py`

**Interfaces:**
- Consumes: `clinic.phone_number_id`, `clinic.whatsapp_token`.
- Produces: `Settings.messages_url_for(phone_number_id: str) -> str`; `WhatsAppClient.send_text(clinic: ClinicConfig, to: str, text: str) -> None`; `FakeWhatsApp.sent: list[tuple[str, str, str]]` as `(clinic_id, to, text)`.

- [ ] **Step 1: Rewrite the sender tests**

Replace everything in `tests/test_whatsapp_service.py` from `def _settings()` to the end of the file with:

```python
def _settings() -> Settings:
    return Settings(
        whatsapp_token="token-123",
        whatsapp_api_version="v20.0",
        whatsapp_verify_token="verify-token",
        llm_api_key="test-key",
    )


def _clinic(token: str | None = None) -> ClinicConfig:
    return GREENFIELD.model_copy(update={"phone_number_id": "phone-id", "whatsapp_token": token})


@pytest.mark.asyncio
async def test_send_text_posts_to_the_clinics_number_with_shared_token() -> None:
    response = FakeResponse()
    http = FakeAsyncClient(response)
    client = WhatsAppClient(_settings(), http)  # type: ignore[arg-type]

    await client.send_text(_clinic(), "2348012345678", "Hello")

    assert http.calls == [
        {
            "url": "https://graph.facebook.com/v20.0/phone-id/messages",
            "json": {
                "messaging_product": "whatsapp",
                "to": "2348012345678",
                "type": "text",
                "text": {"body": "Hello"},
            },
            "headers": {"Authorization": "Bearer token-123"},
        }
    ]
    assert response.raise_for_status_called is True


@pytest.mark.asyncio
async def test_send_text_prefers_the_clinics_own_token() -> None:
    http = FakeAsyncClient(FakeResponse())
    client = WhatsAppClient(_settings(), http)  # type: ignore[arg-type]

    await client.send_text(_clinic(token="clinic-token"), "2348012345678", "Hello")

    assert http.calls[0]["headers"] == {"Authorization": "Bearer clinic-token"}


@pytest.mark.asyncio
async def test_send_text_surfaces_graph_api_failure() -> None:
    request = httpx.Request("POST", "https://graph.facebook.com/v20.0/phone-id/messages")
    response = httpx.Response(500, request=request)
    error = httpx.HTTPStatusError("server error", request=request, response=response)
    http = FakeAsyncClient(FakeResponse(error))
    client = WhatsAppClient(_settings(), http)  # type: ignore[arg-type]

    with pytest.raises(httpx.HTTPStatusError):
        await client.send_text(_clinic(), "2348012345678", "Hello")
```

Add these imports at the top of the file, after `from app.config import Settings`:

```python
from app.models.clinic import ClinicConfig
from conftest import GREENFIELD
```

- [ ] **Step 2: Update the fake and the webhook assertions**

In `tests/conftest.py`, replace `FakeWhatsApp` with:

```python
class FakeWhatsApp:
    """Records outbound sends as (clinic_id, to, text) instead of hitting the Graph API."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str]] = []

    async def send_text(self, clinic: ClinicConfig, to: str, text: str) -> None:
        self.sent.append((clinic.id, to, text))
```

In `tests/test_webhook.py`:

- In `test_inbound_text_triggers_reply`, change the last assertion to
  `assert fake_whatsapp.sent == [("sunrise-dental", "2348012345678", fake_llm.reply_text)]`.
- In `test_webhook_processes_first_text_across_entries`, change the last assertion the same way.
- In `test_downstream_whatsapp_failure_returns_200`, change the stub to
  `async def fail_send_text(clinic: Any, to: str, text: str) -> None:`.
- In `test_message_to_second_clinic_number_is_processed`, replace `assert len(fake_whatsapp.sent) == 1` with
  `assert fake_whatsapp.sent == [("greenfield-medical", "2348012345678", fake_llm.reply_text)]`.

- [ ] **Step 3: Run the tests to verify they fail**

Run: `pytest tests/test_whatsapp_service.py tests/test_webhook.py -v`
Expected: sender tests FAIL with `TypeError: send_text() takes 3 positional arguments but 4 were given`; the four edited webhook tests FAIL on the changed assertion or stub signature.

- [ ] **Step 4: Replace the single-number settings with a URL builder**

Replace the whole of `src/app/config.py` with:

```python
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # WhatsApp Cloud API. The token is the shared app token; a clinic may override
    # it in its YAML. Phone numbers live in the clinic configs, not here.
    whatsapp_token: str = ""
    whatsapp_verify_token: str = ""
    whatsapp_api_version: str = "v20.0"

    # Clinics: directory of per-clinic YAML files (one file per clinic)
    clinics_dir: str = "clinics"

    # LLM (OpenAI-compatible)
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str | None = None

    # Conversation
    max_history_turns: int = 12

    def messages_url_for(self, phone_number_id: str) -> str:
        return (
            f"https://graph.facebook.com/{self.whatsapp_api_version}"
            f"/{phone_number_id}/messages"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 5: Make the sender per-clinic**

Replace the whole of `src/app/services/whatsapp.py` with:

```python
"""Async outbound WhatsApp sender using the Meta Graph API.

Every send goes out through the clinic's own phone_number_id, with the clinic's
token if it has one and the shared app token otherwise.
"""

from __future__ import annotations

import httpx

from app.config import Settings
from app.models.clinic import ClinicConfig


class WhatsAppClient:
    def __init__(self, settings: Settings, http: httpx.AsyncClient) -> None:
        self._settings = settings
        self._http = http

    async def send_text(self, clinic: ClinicConfig, to: str, text: str) -> None:
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": text},
        }
        token = clinic.whatsapp_token or self._settings.whatsapp_token
        headers = {"Authorization": f"Bearer {token}"}
        url = self._settings.messages_url_for(clinic.phone_number_id)
        response = await self._http.post(url, json=payload, headers=headers)
        response.raise_for_status()
```

- [ ] **Step 6: Pass the clinic from the route**

In `src/app/routes/webhook.py`, change the send line inside the `try` block to:

```python
        await state.whatsapp.send_text(clinic, phone, reply)
```

- [ ] **Step 7: Update `.env.example`**

Replace the whole file with:

```
# WhatsApp Cloud API (Meta Graph API)
# Shared app access token. A clinic can override it with `whatsapp_token` in its YAML.
WHATSAPP_TOKEN=your-permanent-or-temp-access-token
WHATSAPP_VERIFY_TOKEN=any-string-you-choose-for-webhook-verification
WHATSAPP_API_VERSION=v20.0

# Directory of per-clinic YAML files. Each file sets its own phone_number_id.
CLINICS_DIR=clinics

# LLM (OpenAI-compatible). base_url is optional; set it to swap providers.
LLM_API_KEY=your-llm-api-key
LLM_MODEL=gpt-4o-mini
LLM_BASE_URL=

# Conversation history kept in memory per (clinic, phone number), in turns
MAX_HISTORY_TURNS=12
```

- [ ] **Step 8: Run the tests to verify they pass**

Run: `pytest tests/test_whatsapp_service.py tests/test_webhook.py -v`
Expected: 3 + 15 = 18 passed.

- [ ] **Step 9: Lint and run the full suite**

Run: `ruff check . && pytest -q`
Expected: `All checks passed!` and `60 passed`. Confirm the old setting is gone:

```bash
grep -rn "whatsapp_phone_number_id\|whatsapp_messages_url" src tests .env.example
```

Expected: no output.

- [ ] **Step 10: Commit**

```bash
git add src/app/config.py src/app/services/whatsapp.py src/app/routes/webhook.py tests/conftest.py tests/test_whatsapp_service.py tests/test_webhook.py .env.example
git commit -m "feat(m1): send replies through the clinic's own phone_number_id and token"
```

---

### Task 8: F1 acceptance tests, degenerate case, and docs

**Files:**
- Test: `tests/test_webhook.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: everything above. No new production code.

- [ ] **Step 1: Write the acceptance tests**

Append to `tests/test_webhook.py`:

```python
def test_f1_acceptance_clinic_a_answers_with_a_facts_never_b(client, fake_llm: Any, fake_whatsapp: Any):
    """PRD F1: a message to clinic A's number answers with A's prices and never B's."""
    client.post(
        "/webhook",
        json=_inbound_payload("2348012345678", "How much is a root canal?"),
    )
    client.post(
        "/webhook",
        json=_inbound_payload(
            "2348098765432", "How much is a malaria test?", phone_number_id=GREENFIELD_PHONE_NUMBER_ID
        ),
    )

    sunrise_prompt, greenfield_prompt = fake_llm.system_prompts
    assert "Root Canal Treatment — 90,000–120,000" in sunrise_prompt
    assert "Greenfield" not in sunrise_prompt
    assert "Malaria Test — 5,000" in greenfield_prompt
    assert "Sunrise" not in greenfield_prompt

    assert fake_whatsapp.sent == [
        ("sunrise-dental", "2348012345678", fake_llm.reply_text),
        ("greenfield-medical", "2348098765432", fake_llm.reply_text),
    ]


def test_f1_acceptance_single_clinic_deployment_behaves_identically(
    single_clinic_client, fake_llm: Any, fake_whatsapp: Any
):
    """PRD F1 degenerate case: one config, same behaviour as the single-tenant demo."""
    resp = single_clinic_client.post("/webhook", json=_inbound_payload("2348012345678", "Hello"))

    assert resp.status_code == 200
    assert fake_llm.calls[0][-1] == {"role": "user", "content": "Hello"}
    assert "Sunrise Dental & Family Clinic" in fake_llm.system_prompts[0]
    assert fake_whatsapp.sent == [("sunrise-dental", "2348012345678", fake_llm.reply_text)]

    # A number that belongs to no clinic in a one-clinic deployment is dropped, not misrouted.
    resp = single_clinic_client.post(
        "/webhook",
        json=_inbound_payload("2348012345678", "Hello", phone_number_id=GREENFIELD_PHONE_NUMBER_ID),
    )
    assert resp.status_code == 200
    assert len(fake_whatsapp.sent) == 1
```

- [ ] **Step 2: Run the tests to verify they pass**

Run: `pytest tests/test_webhook.py -v`
Expected: 17 passed. If either acceptance test fails, the bug is in an earlier task, not in the test; fix it there.

- [ ] **Step 3: Update the README**

Replace the whole of `README.md` with:

````markdown
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
````

- [ ] **Step 4: Lint and run the full suite one last time**

Run: `ruff check . && pytest -q`
Expected: `All checks passed!` and `62 passed`.

- [ ] **Step 5: Prove the degenerate case against the real directory**

```bash
CLINICS_DIR=clinics python -c "
from fastapi.testclient import TestClient
from app.main import app
with TestClient(app) as c:
    print(len(app.state.clinics), c.get('/health').json())
"
```

Expected output: `1 {'status': 'ok'}`.

- [ ] **Step 6: Commit**

```bash
git add tests/test_webhook.py README.md
git commit -m "test(m1): F1 acceptance tests and README for multi-clinic setup"
```

---

## Self-review against the PRD (F1)

| PRD F1 requirement | Task |
|---|---|
| Per-clinic YAML on the persistent volume with the listed fields incl. `phone_number_id`, staff number, optional token | 1, 2, 4 (`clinics_dir` setting points at the volume in M4) |
| `prompts.py` becomes a template; rules fixed, `CLINIC PROFILE` rendered; Sunrise is just YAML | 4 (YAML), 6 (template) |
| Parse `value.metadata.phone_number_id`; add `metadata` to `Value` | 3 |
| Unknown `phone_number_id` → log and return 200 | 4 |
| `ConversationStore` keyed by `(clinic_id, phone)` | 5 |
| Degenerate case: one config behaves identically | 8 (`single_clinic_client`) plus `test_lifespan_loads_clinics_from_clinics_dir` in 4 |
| Acceptance: two configs loaded; A answers with A's prices never B's; one-config passes the suite | 8 |
| Risk table: prompt-integrity tests generalized to per-clinic rendering | 6 |

Not in this plan, by design: staff notifications, SQLite, tool calling (F2); fallback on error, non-text reply, signature check, throttle (F3). `staff_phone` is loaded but unused until M2.

## Test count checkpoints

| After task | Expected `pytest -q` |
|---|---|
| Setup | 26 passed |
| 1 | 35 passed |
| 2 | 46 passed |
| 3 | 48 passed |
| 4 | 52 passed |
| 5 | 54 passed |
| 6 | 59 passed |
| 7 | 60 passed |
| 8 | 62 passed |

If a count is off by one or two, list the collected tests with `pytest --collect-only -q` and compare against the tests named in the task before assuming a bug.
