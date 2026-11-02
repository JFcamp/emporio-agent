from collections.abc import Sequence
from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult


class FakeChatModel(BaseChatModel):
    """Modelo falso roteirizado para testes do grafo, sem rede nem LLM real.

    Recebe uma lista de AIMessages e as devolve em ordem a cada invocação.
    Guarda em `received_calls` as listas de mensagens que viu, para inspeção.
    bind_tools devolve a si mesmo (o roteiro já define as tool calls).
    """

    responses: list[AIMessage]
    received_calls: list[list[BaseMessage]]
    cursor: int
    raises: bool
    raise_after: int | None

    def __init__(
        self,
        responses: list[AIMessage] | None = None,
        raises: bool = False,
        raise_after: int | None = None,
    ):
        super().__init__(
            responses=responses or [],
            received_calls=[],
            cursor=0,
            raises=raises,
            raise_after=raise_after,
        )

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        self.received_calls.append(list(messages))
        if self.raises:
            raise RuntimeError("falha simulada do modelo")
        # raise_after=N: emite N respostas e levanta exceção na chamada N+1.
        if self.raise_after is not None and self.cursor >= self.raise_after:
            raise RuntimeError("falha simulada do modelo")
        if self.cursor < len(self.responses):
            message = self.responses[self.cursor]
            self.cursor += 1
        else:
            message = AIMessage(content="")
        return ChatResult(generations=[ChatGeneration(message=message)])

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> "FakeChatModel":
        return self

    @property
    def _llm_type(self) -> str:
        return "fake-chat-model"
