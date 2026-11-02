import pytest

from emporio.agent.graph import Reply, ToolCall
from emporio.interfaces import cli


class _FakeAgent:
    def __init__(self, *args, **kwargs):
        pass

    @staticmethod
    def new_thread_id():
        return "fake-thread"

    def history(self, thread_id):
        return []

    def chat(self, message, thread_id):
        return Reply(
            text="Claro! Posso ajudar com isso.",
            tool_calls=[ToolCall(name="buscar_produtos", args={"termo": "violão"}, result="{}")],
        )


def _make_console(monkeypatch, inputs):
    from rich.console import Console

    console = Console(record=True, width=100)
    responses = iter(inputs)
    monkeypatch.setattr(console, "input", lambda *a, **k: next(responses))
    # status() abre um spinner animado; troca por um contexto nulo nos testes.
    from contextlib import nullcontext

    monkeypatch.setattr(console, "status", lambda *a, **k: nullcontext())
    monkeypatch.setattr(cli, "Console", lambda *a, **k: console)
    return console


def test_cli_flow(monkeypatch):
    monkeypatch.setattr(cli, "EmporioAgent", _FakeAgent)
    monkeypatch.setattr(cli, "ensure_data", lambda *a, **k: None)
    monkeypatch.setattr(cli, "describe", lambda *a, **k: "groq:fake")
    monkeypatch.setattr("sys.argv", ["emporio"])

    console = _make_console(
        monkeypatch,
        ["oi", "/debug", "tudo bem?", "/novo", "", "/sair"],
    )

    cli.main()
    output = console.export_text()

    assert "Claro! Posso ajudar com isso." in output
    assert "Nova conversa:" in output
    assert "Para retomar esta conversa" in output

    # A linha "↳" só aparece depois do /debug: antes de ligar (1º turno "oi")
    # não há ferramenta exibida; depois do /debug (turno "tudo bem?") sim.
    first_reply = output.index("Claro! Posso ajudar com isso.")
    debug_line = output.index("Debug ligado")
    arrow = output.index("↳ buscar_produtos")
    assert first_reply < debug_line < arrow


def test_cli_runtime_error_exits_1(monkeypatch):
    def _boom(*args, **kwargs):
        raise RuntimeError("GROQ_API_KEY não definida.")

    monkeypatch.setattr(cli, "EmporioAgent", _boom)
    monkeypatch.setattr(cli, "ensure_data", lambda *a, **k: None)
    monkeypatch.setattr(cli, "describe", lambda *a, **k: "groq:fake")
    monkeypatch.setattr("sys.argv", ["emporio"])
    _make_console(monkeypatch, [])

    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 1
