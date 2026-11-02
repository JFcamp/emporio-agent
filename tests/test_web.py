import importlib.util

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from emporio.agent import graph
from emporio.agent.graph import Reply, ToolCall

# Caminho absoluto para o script, sem importar/executar o módulo aqui.
WEB_PATH = importlib.util.find_spec("emporio.interfaces.web").origin


class _FakeAgent:
    def __init__(self, *args, **kwargs):
        pass

    @staticmethod
    def new_thread_id():
        return "web-thread"

    def history(self, thread_id):
        return []

    def chat(self, message, thread_id):
        return Reply(
            text="Resposta de teste",
            tool_calls=[ToolCall("buscar_produtos", {"categoria": "Violões"}, "{}")],
        )


@pytest.fixture
def patched(monkeypatch):
    monkeypatch.setattr(graph, "EmporioAgent", _FakeAgent)
    monkeypatch.setattr("emporio.bootstrap.ensure_data", lambda *a, **k: None)
    monkeypatch.setattr("emporio.interfaces.common.setup_logging", lambda *a, **k: None)
    yield
    st.cache_resource.clear()


def _texts(at):
    chunks = []
    for collection in (at.markdown, at.title, at.caption):
        chunks.extend(item.value for item in collection)
    return "\n".join(chunks)


def test_renders_welcome_and_suggestions(patched):
    at = AppTest.from_file(WEB_PATH).run()
    assert not at.exception
    text = _texts(at)
    assert "Empório da Música" in text
    assert "Eu sou a Lia" in text
    labels = {b.label for b in at.button}
    assert {"Violões até R$ 1.000", "Promoções de hoje",
            "Status do meu pedido", "Como funciona a devolução?"} <= labels


def test_suggestion_button_sends_message(patched):
    at = AppTest.from_file(WEB_PATH).run()
    promo = next(b for b in at.button if b.label == "Promoções de hoje")
    promo.click().run()

    text = _texts(at)
    assert "Quais promoções estão ativas hoje?" in text
    assert "Resposta de teste" in text
    # Sugestões somem quando já há turnos.
    labels = {b.label for b in at.button}
    assert "Promoções de hoje" not in labels


def test_chat_input_shows_reply(patched):
    at = AppTest.from_file(WEB_PATH).run()
    at.chat_input[0].set_value("tem guitarra?").run()
    assert "Resposta de teste" in _texts(at)


def test_toggle_shows_tools_expander(patched):
    at = AppTest.from_file(WEB_PATH).run()
    at.toggle[0].set_value(True).run()
    at.chat_input[0].set_value("tem guitarra?").run()
    labels = [exp.label for exp in at.expander]
    assert any("Ferramentas usadas (1)" in label for label in labels)


def test_new_conversation_clears_history(patched):
    at = AppTest.from_file(WEB_PATH).run()
    at.chat_input[0].set_value("oi").run()
    assert "Resposta de teste" in _texts(at)

    nova = next(b for b in at.button if b.label == "Nova conversa")
    nova.click().run()

    labels = {b.label for b in at.button}
    assert "Promoções de hoje" in labels  # sugestões voltaram
    assert "Resposta de teste" not in _texts(at)


def test_runtime_error_shows_st_error(patched, monkeypatch):
    def _boom(*args, **kwargs):
        raise RuntimeError("GROQ_API_KEY não definida.")

    monkeypatch.setattr(graph, "EmporioAgent", _boom)
    at = AppTest.from_file(WEB_PATH).run()
    assert any("GROQ_API_KEY" in err.value for err in at.error)
