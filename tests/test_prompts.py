"""Tests for demo-critical prompt facts and safety rules."""

from __future__ import annotations

from app.prompts import SYSTEM_PROMPT


def test_prompt_contains_clinic_identity_and_location() -> None:
    assert "Sunrise Dental & Family Clinic" in SYSTEM_PROMPT
    assert "Wuse 2, Abuja" in SYSTEM_PROMPT
    assert "14 Aminu Kano Crescent" in SYSTEM_PROMPT
    assert "opposite Sherif Plaza" in SYSTEM_PROMPT


def test_prompt_contains_demo_critical_prices_and_hmo_list() -> None:
    assert "Root Canal Treatment — 90,000–120,000" in SYSTEM_PROMPT
    assert "Scaling & Polishing (cleaning) — 25,000" in SYSTEM_PROMPT
    assert "Braces / Orthodontics — from 450,000" in SYSTEM_PROMPT
    assert "Hygeia, AXA Mansard, Reliance HMO, Leadway Health" in SYSTEM_PROMPT


def test_prompt_contains_safety_and_handoff_rules() -> None:
    assert "Never give medical advice" in SYSTEM_PROMPT
    assert "No diagnosis, no treatment suggestions" in SYSTEM_PROMPT
    assert "This sounds urgent. Please call us right now on 0803 XXX XXXX" in SYSTEM_PROMPT
    assert "I'll connect you with our front desk team — they'll reply here shortly." in SYSTEM_PROMPT


def test_prompt_contains_booking_confirmation_markers() -> None:
    assert "✅ Appointment confirmed" in SYSTEM_PROMPT
    assert "👤 [Name]" in SYSTEM_PROMPT
    assert "🦷 [Service]" in SYSTEM_PROMPT
    assert "📅 [Day, Date — Time]" in SYSTEM_PROMPT
    assert "Reply RESCHEDULE or CANCEL anytime." in SYSTEM_PROMPT


def test_prompt_contains_bot_disclosure() -> None:
    assert "Yes — I'm Sunrise Dental's virtual assistant." in SYSTEM_PROMPT
    assert "book appointments 24/7" in SYSTEM_PROMPT
