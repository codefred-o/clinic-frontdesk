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
