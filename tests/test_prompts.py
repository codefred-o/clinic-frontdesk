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
