from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_provider: Literal["anthropic", "openai", "ollama"] = "ollama"

    # Anthropic
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    # Ollama (OpenAI-compatible, no key needed)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"

    discovery_api_url: str = "http://localhost:8003"
    permit_service_url: str = "http://localhost:8002"


settings = Settings()
