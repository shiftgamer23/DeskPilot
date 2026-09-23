"""Provider-agnostic chat model factory. Agent code calls get_llm() and never imports a vendor SDK."""
from langchain_core.language_models.chat_models import BaseChatModel

from app import config


def get_llm(provider: str | None = None, temperature: float = 0.0) -> BaseChatModel:
    provider = (provider or config.LLM_PROVIDER).lower()
    if provider == "groq":
        from langchain_groq import ChatGroq

        return ChatGroq(model=config.GROQ_MODEL, api_key=config.GROQ_API_KEY, temperature=temperature)
    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=config.GEMINI_MODEL, google_api_key=config.GEMINI_API_KEY, temperature=temperature
        )
    raise ValueError(f"Unknown LLM provider: {provider!r} (expected 'groq' or 'gemini')")
