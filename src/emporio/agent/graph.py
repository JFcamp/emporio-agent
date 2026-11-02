"""Grafo explícito do agente Lia.

Fluxo: START → agent ⇄ tools → END.

O nó "agent" chama o modelo com o prompt dinâmico (montado a cada turno) à
frente do histórico; a aresta condicional (tools_condition) manda para o nó
"tools" quando o modelo pede ferramentas e volta para "agent" com os resultados,
até o modelo responder sem tool calls (END).

O grafo é explícito, e não um ReAct pronto, porque precisamos de três pontos de
controle entre os passos: injetar o system prompt dinâmico (horário/loja/
categorias) a cada chamada, limpar tool calls órfãs que uma interrupção possa
deixar, e cortar o histórico por número de mensagens antes de enviar ao provedor.
"""

import logging
import re
import sqlite3
import uuid
from dataclasses import dataclass

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    SystemMessage,
    ToolMessage,
    trim_messages,
)
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from emporio.agent.llm import build_llm
from emporio.agent.prompts import build_system_prompt
from emporio.config import get_settings
from emporio.tools import ALL_TOOLS

logger = logging.getLogger(__name__)

FALLBACK = (
    "Tive um probleminha técnico aqui. Pode repetir a pergunta? Se preferir, "
    "fale com a equipe pelo WhatsApp (67) 3341-4444."
)

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def drop_orphan_tool_calls(messages: list[BaseMessage]) -> list[BaseMessage]:
    # Evita que uma interrupção (ex.: limite de passos) deixe o histórico
    # inválido e o provedor recuse o turno seguinte: remove AIMessages cujos
    # tool_calls não têm ToolMessage correspondente e ToolMessages sem origem.
    answered_ids = {
        msg.tool_call_id for msg in messages if isinstance(msg, ToolMessage)
    }
    ai_call_ids: set[str] = set()
    for msg in messages:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            ai_call_ids.update(call["id"] for call in msg.tool_calls)

    cleaned: list[BaseMessage] = []
    for msg in messages:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            missing = [c for c in msg.tool_calls if c["id"] not in answered_ids]
            if missing:
                continue
        if isinstance(msg, ToolMessage) and msg.tool_call_id not in ai_call_ids:
            continue
        cleaned.append(msg)
    return cleaned


def build_graph(llm: BaseChatModel, checkpointer=None, max_history: int | None = None):
    model = llm.bind_tools(ALL_TOOLS)
    limit = max_history if max_history is not None else get_settings().max_history_messages

    def agent_node(state: MessagesState) -> dict:
        history = drop_orphan_tool_calls(state["messages"])
        history = trim_messages(
            history,
            strategy="last",
            token_counter=len,
            max_tokens=limit,
            start_on="human",
            include_system=False,
        )
        response = model.invoke([SystemMessage(build_system_prompt()), *history])
        return {"messages": [response]}

    graph = StateGraph(MessagesState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", ToolNode(ALL_TOOLS, handle_tool_errors=True))
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", tools_condition)
    graph.add_edge("tools", "agent")
    return graph.compile(checkpointer=checkpointer)


@dataclass
class ToolCall:
    name: str
    args: dict
    result: str


@dataclass
class Reply:
    text: str
    tool_calls: list[ToolCall]


def clean_text(text: str) -> str:
    return _THINK_RE.sub("", text).strip()


def _text_from(message: AIMessage) -> str:
    content = message.content
    if isinstance(content, str):
        return clean_text(content)
    parts: list[str] = []
    for part in content:
        if isinstance(part, str):
            parts.append(part)
        elif isinstance(part, dict) and part.get("type") == "text":
            parts.append(part.get("text", ""))
    return clean_text("".join(parts))


class EmporioAgent:
    def __init__(self, llm: BaseChatModel | None = None, persist: bool = True):
        self._llm = llm or build_llm()
        if persist:
            settings = get_settings()
            settings.checkpoints_db.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(settings.checkpoints_db, check_same_thread=False)
            self._checkpointer = SqliteSaver(conn)
        else:
            self._checkpointer = InMemorySaver()
        self._graph = build_graph(self._llm, checkpointer=self._checkpointer)

    @staticmethod
    def new_thread_id() -> str:
        return uuid.uuid4().hex[:12]

    def history(self, thread_id: str) -> list[BaseMessage]:
        config = {"configurable": {"thread_id": thread_id}}
        state = self._graph.get_state(config)
        if not state.values:
            return []
        return state.values.get("messages", [])

    def chat(self, message: str, thread_id: str) -> Reply:
        config = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": 16,
        }
        try:
            previous = len(self.history(thread_id))
            result = self._graph.invoke({"messages": [("user", message)]}, config)
            new_messages = result["messages"][previous:]
            return _build_reply(new_messages)
        except Exception:
            logger.exception("Falha ao processar mensagem na thread %s", thread_id)
            return Reply(FALLBACK, [])


def _build_reply(new_messages: list[BaseMessage]) -> Reply:
    results_by_id: dict[str, str] = {}
    for msg in new_messages:
        if isinstance(msg, ToolMessage):
            results_by_id[msg.tool_call_id] = (
                msg.content if isinstance(msg.content, str) else str(msg.content)
            )

    tool_calls: list[ToolCall] = []
    last_ai_text = ""
    for msg in new_messages:
        if isinstance(msg, AIMessage):
            if msg.tool_calls:
                for call in msg.tool_calls:
                    tool_calls.append(
                        ToolCall(
                            name=call["name"],
                            args=call.get("args", {}),
                            result=results_by_id.get(call["id"], ""),
                        )
                    )
            text = _text_from(msg)
            if text:
                last_ai_text = text

    return Reply(last_ai_text or FALLBACK, tool_calls)
