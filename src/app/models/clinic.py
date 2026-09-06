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
