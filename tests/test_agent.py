import json
import logging
from datetime import datetime

import pytest
from fakes import FakeChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from emporio.agent.graph import (
    FALLBACK,
    EmporioAgent,
    clean_text,
    drop_orphan_tool_calls,
)
from emporio.agent.llm import build_llm, describe
from emporio.agent.prompts import build_system_prompt
from emporio.config import STORE_TZ, Settings, get_settings


def _tool_call_msg(name, args, call_id):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])


def test_tool_flow():
    script = [
        _tool_call_msg("detalhar_produto", {"nome_ou_id": "Takamine GD20"}, "c1"),
        AIMessage(content="O Takamine GD20 sai por R$ 2.199,00."),
    ]
    agent = EmporioAgent(llm=FakeChatModel(responses=script), persist=False)
    reply = agent.chat("quanto custa o Takamine GD20?", agent.new_thread_id())

    assert reply.text == "O Takamine GD20 sai por R$ 2.199,00."
    assert reply.tool_calls[0].name == "detalhar_produto"
    assert '"id": 95' in reply.tool_calls[0].result


def test_history_persists_and_threads_isolated():
    script = [AIMessage(content="Oi!"), AIMessage(content="De novo oi!")]
    agent = EmporioAgent(llm=FakeChatModel(responses=script), persist=False)
    t1 = agent.new_thread_id()
    agent.chat("oi", t1)
    agent.chat("tudo bem?", t1)
    assert len(agent.history(t1)) >= 4  # 2 humanas + 2 IA

    t2 = agent.new_thread_id()
    assert agent.history(t2) == []


def test_first_message_is_system_with_lia():
    fake = FakeChatModel(responses=[AIMessage(content="Olá!")])
    agent = EmporioAgent(llm=fake, persist=False)
    agent.chat("oi", agent.new_thread_id())
    first = fake.received_calls[0][0]
    assert isinstance(first, SystemMessage)
    assert "Lia" in first.content


def test_history_trimming():
    from langgraph.checkpoint.memory import InMemorySaver

    from emporio.agent.graph import build_graph

    responses = [AIMessage(content=f"resposta {i}") for i in range(10)]
    fake = FakeChatModel(responses=responses)
    graph = build_graph(fake, checkpointer=InMemorySaver(), max_history=4)
    config = {"configurable": {"thread_id": "t-trim"}, "recursion_limit": 16}
    for i in range(6):
        graph.invoke({"messages": [("user", f"mensagem {i}")]}, config)

    last_seen = fake.received_calls[-1]
    assert isinstance(last_seen[0], SystemMessage)
    assert len(last_seen) <= 1 + 4
    assert isinstance(last_seen[1], HumanMessage)


def test_drop_orphan_tool_calls():
    orphan_ai = _tool_call_msg("buscar_politica", {"pergunta": "x"}, "orphan")
    complete_ai = _tool_call_msg("buscar_politica", {"pergunta": "y"}, "ok")
    complete_tool = ToolMessage(content="{}", tool_call_id="ok")
    stray_tool = ToolMessage(content="{}", tool_call_id="stray")
    human = HumanMessage(content="oi")

    cleaned = drop_orphan_tool_calls(
        [human, orphan_ai, complete_ai, complete_tool, stray_tool]
    )
    assert orphan_ai not in cleaned
    assert complete_ai in cleaned
    assert complete_tool in cleaned
    assert stray_tool not in cleaned
    assert human in cleaned


def test_drop_orphan_removes_partial_tool_response():
    # AIMessage com 2 tool_calls mas só 1 ToolMessage: ambos saem.
    ai = AIMessage(
        content="",
        tool_calls=[
            {"name": "buscar_politica", "args": {"pergunta": "a"}, "id": "a"},
            {"name": "buscar_politica", "args": {"pergunta": "b"}, "id": "b"},
        ],
    )
    partial_tool = ToolMessage(content="{}", tool_call_id="a")
    human = HumanMessage(content="oi")

    cleaned = drop_orphan_tool_calls([human, ai, partial_tool])
    assert ai not in cleaned
    assert partial_tool not in cleaned
    assert human in cleaned


def test_trim_keeps_human_of_current_turn():
    from langgraph.checkpoint.memory import InMemorySaver

    from emporio.agent.graph import build_graph

    # Turno: Human + AI(tool) + Tool + AI(tool) + Tool + AI(texto).
    responses = [
        _tool_call_msg("buscar_politica", {"pergunta": "frete"}, "t1"),
        _tool_call_msg("buscar_politica", {"pergunta": "troca"}, "t2"),
        AIMessage(content="Pronto!"),
    ]
    fake = FakeChatModel(responses=responses)
    graph = build_graph(fake, checkpointer=InMemorySaver(), max_history=3)
    config = {"configurable": {"thread_id": "t-human"}, "recursion_limit": 16}
    graph.invoke({"messages": [("user", "me explica frete e troca")]}, config)

    last_seen = fake.received_calls[-1]
    humans = [m for m in last_seen if isinstance(m, HumanMessage)]
    assert any("frete e troca" in m.content for m in humans)


def test_model_exception_returns_fallback(caplog):
    agent = EmporioAgent(llm=FakeChatModel(raises=True), persist=False)
    with caplog.at_level(logging.ERROR):
        reply = agent.chat("oi", agent.new_thread_id())
    assert reply.text == FALLBACK
    assert "falha simulada do modelo" not in reply.text
    assert "RuntimeError" not in reply.text
    assert any("falha simulada do modelo" in rec.message or rec.exc_info for rec in caplog.records)


def test_clean_text_removes_think():
    assert clean_text("<think>raciocínio</think>  Olá!") == "Olá!"


def test_format_currency():
    from emporio.agent.graph import format_currency

    assert format_currency("R$429,90") == "R$ 429,90"
    assert format_currency("R$  1.000,00") == "R$ 1.000,00"
    assert format_currency("R$ 549,00") == "R$ 549,00"
    assert format_currency("sem dinheiro aqui") == "sem dinheiro aqui"


def test_provider_failure_after_handoff_does_not_duplicate_protocol():
    from emporio.agent.graph import build_graph
    from emporio.config import get_settings

    handoff_call = _tool_call_msg(
        "encaminhar_atendente",
        {"motivo": "reclamacao", "resumo": "entregador grosseiro"},
        "h1",
    )

    # Turno 1: encaminha e, na chamada seguinte, o provedor falha.
    fake1 = FakeChatModel(responses=[handoff_call], raise_after=1)
    agent = EmporioAgent(llm=fake1, persist=False)
    thread_id = agent.new_thread_id()
    reply1 = agent.chat("quero reclamar do pedido 8", thread_id)
    assert reply1.text == FALLBACK

    path = get_settings().handoffs_file
    lines_after_1 = [
        line for line in path.read_text(encoding="utf-8").splitlines() if thread_id in line
    ]
    assert len(lines_after_1) == 1

    # Turno 2 (mesma thread): encaminha de novo e depois responde normalmente.
    handoff_call_2 = _tool_call_msg(
        "encaminhar_atendente",
        {"motivo": "reclamacao", "resumo": "entregador grosseiro"},
        "h2",
    )
    fake2 = FakeChatModel(
        responses=[handoff_call_2, AIMessage(content="Registrei, segue o protocolo.")]
    )
    agent._graph = build_graph(fake2, checkpointer=agent._checkpointer)

    reply2 = agent.chat("e aí, conseguiu registrar?", thread_id)

    # O protocolo do turno 2 é o mesmo e vem como já registrado.
    handoff_result = next(
        c.result for c in reply2.tool_calls if c.name == "encaminhar_atendente"
    )
    assert '"ja_registrado": true' in handoff_result

    lines_after_2 = [
        line for line in path.read_text(encoding="utf-8").splitlines() if thread_id in line
    ]
    assert len(lines_after_2) == 1  # não duplicou

    # O histórico não guardou tool call órfã: a última chamada ao modelo no
    # turno 2 não recebeu AIMessage com tool_calls sem ToolMessage de resposta.
    last_seen = fake2.received_calls[-1]
    answered = {m.tool_call_id for m in last_seen if isinstance(m, ToolMessage)}
    for msg in last_seen:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            assert all(call["id"] in answered for call in msg.tool_calls)


def test_handoff_records_thread_id():
    script = [
        _tool_call_msg(
            "encaminhar_atendente",
            {"motivo": "reclamacao", "resumo": "cliente insatisfeito"},
            "h1",
        ),
        AIMessage(content="Registrei seu caso, protocolo a caminho."),
    ]
    agent = EmporioAgent(llm=FakeChatModel(responses=script), persist=False)
    thread_id = agent.new_thread_id()
    agent.chat("quero reclamar", thread_id)

    path = get_settings().handoffs_file
    records = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert any(r.get("conversa") == thread_id for r in records)


def test_system_prompt_monday_open():
    monday = datetime(2026, 3, 2, 10, 0, tzinfo=STORE_TZ)
    prompt = build_system_prompt(monday)
    assert "ABERTA" in prompt
    assert "3341-4444" in prompt
    assert "Violões (" in prompt


def test_system_prompt_sunday_closed():
    sunday = datetime(2026, 3, 8, 10, 0, tzinfo=STORE_TZ)
    prompt = build_system_prompt(sunday)
    assert "FECHADA" in prompt
    assert "amanhã às 09:00" in prompt


def test_system_prompt_uses_reference_date(monkeypatch):
    from datetime import date as _date

    settings = get_settings()
    monkeypatch.setattr(settings, "reference_date", _date(2026, 3, 8))  # domingo
    prompt = build_system_prompt()  # sem now explícito -> usa reference_date
    assert "Domingo" in prompt
    assert "08/03/2026" in prompt


def test_build_llm_groq_without_key_raises():
    settings = Settings(_env_file=None, llm_provider="groq", groq_api_key=None)
    with pytest.raises(RuntimeError):
        build_llm(settings)


def test_build_llm_groq_with_key():
    settings = Settings(_env_file=None, llm_provider="groq", groq_api_key="fake-key")
    llm = build_llm(settings)
    assert type(llm).__name__ == "ChatGroq"
    assert describe(settings) == f"groq:{settings.groq_model}"


def test_build_llm_ollama():
    settings = Settings(_env_file=None, llm_provider="ollama")
    llm = build_llm(settings)
    assert type(llm).__name__ == "ChatOllama"
    assert describe(settings) == f"ollama:{settings.ollama_model}"
