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
