"""Single seam between agent code and whichever LLM provider is configured.

No agent/tool/graph code should import langchain_openai (or any provider
SDK) directly — everything goes through get_chat_model(), so switching
LLM_PROVIDER in the environment is the entire migration.
"""

from functools import lru_cache

from langchain_core.language_models.chat_models import BaseChatModel

from src.shared.settings import settings


@lru_cache
def get_chat_model() -> BaseChatModel:
    provider = settings.llm_provider.lower()

    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=settings.llm_model, api_key=settings.openai_api_key, temperature=0)

    if provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(model=settings.llm_model, google_api_key=settings.google_api_key, temperature=0)

    raise ValueError(f"Unsupported LLM_PROVIDER: {provider!r}. Supported: openai, google.")
