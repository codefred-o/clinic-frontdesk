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
