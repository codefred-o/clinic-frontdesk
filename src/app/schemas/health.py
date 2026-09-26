"""Operational endpoint response contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ServiceStatus(BaseModel):
    status: Literal["ok", "unavailable"]
    service: str
    version: str


class ReadinessStatus(ServiceStatus):
    checks: dict[str, Literal["ok", "unavailable"]]
