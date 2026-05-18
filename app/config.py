"""Configuration centrale du module IA."""
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # API
    app_name: str = "ASM IA Module"
    app_version: str = "0.2.0"
    debug: bool = True

    # === LLM PROVIDER ===
    llm_provider: str = "groq"

    # === GROQ (cloud, recommande) ===
    groq_api_key: str = ""
    groq_api_key_2: Optional[str] = None
    groq_api_key_3: Optional[str] = None
    groq_api_key_4: Optional[str] = None
    groq_api_key_5: Optional[str] = None
    groq_api_key_6: Optional[str] = None
    groq_api_key_7: Optional[str] = None
    groq_api_key_8: Optional[str] = None

    groq_model: str = "llama-3.3-70b-versatile"

    # === OLLAMA (local, fallback) ===
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"

    # === SBERT ===
    sbert_model: str = "paraphrase-multilingual-MiniLM-L12-v2"

    # === spaCy ===
    spacy_model: str = "fr_core_news_md"

    # === Tesseract (chemin Windows) ===
    tesseract_cmd: str = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()