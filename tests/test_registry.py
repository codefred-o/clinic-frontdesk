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
