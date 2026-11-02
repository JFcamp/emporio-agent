from langchain_core.language_models import BaseChatModel

from emporio.config import Settings, get_settings


def build_llm(settings: Settings | None = None) -> BaseChatModel:
    settings = settings or get_settings()

    if settings.llm_provider == "groq":
        if not settings.groq_api_key:
            raise RuntimeError(
                "GROQ_API_KEY não definida. Crie uma chave grátis em "
                "https://console.groq.com/keys e coloque no .env "
                "(ou use LLM_PROVIDER=ollama)."
            )
        from langchain_groq import ChatGroq

        return ChatGroq(
            model=settings.groq_model,
            api_key=settings.groq_api_key,
            temperature=settings.llm_temperature,
            max_retries=2,
        )

    from langchain_ollama import ChatOllama

    # reasoning desligado: o modo "pensando" só adiciona latência no atendimento.
    return ChatOllama(
        model=settings.ollama_model,
        base_url=settings.ollama_base_url,
        temperature=settings.llm_temperature,
        reasoning=False,
    )


def describe(settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    if settings.llm_provider == "groq":
        return f"groq:{settings.groq_model}"
    return f"ollama:{settings.ollama_model}"
