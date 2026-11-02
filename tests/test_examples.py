import importlib.util
from pathlib import Path

from emporio.agent.graph import Reply, ToolCall

# Carrega scripts/generate_examples.py como módulo (não é um pacote).
_SPEC = importlib.util.spec_from_file_location(
    "generate_examples",
    Path(__file__).resolve().parents[1] / "scripts" / "generate_examples.py",
)
gen = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(gen)


class _FakeAgent:
    def __init__(self, error_on=None):
        self._error_on = error_on
        self._i = 0

    @staticmethod
    def new_thread_id():
        return "t"

    def chat(self, message, thread_id):
        self._i += 1
        tools = [ToolCall("buscar_produtos", {"categoria": "Violões"}, "{}")]
        error = "rate_limit" if self._error_on == self._i else None
        return Reply("Resposta de teste", tools, error=error)


def test_render_structure():
    turns = [
        {"user": "oi", "tools": [{"name": "buscar_produtos", "args": {"x": 1}}], "reply": "olá"},
        {"user": "tchau", "tools": [], "reply": "até mais"},
    ]
    out = gen.render("Título", "desc", "groq:fake", gen.REFERENCE_DATE, turns)
    assert "# Título" in out
    assert "*desc*" in out
    assert "**Cliente:** oi" in out
    assert "**Lia:** olá" in out
    # bloco <details> só no turno com ferramentas
    assert out.count("<details>") == 1
    assert "buscar_produtos({\"x\": 1})" in out


def test_generate_writes_all_scenarios(tmp_path):
    code = gen.generate(agent_factory=lambda: _FakeAgent(), out_dir=tmp_path, sleep=0)
    assert code == 0
    produced = sorted(p.name for p in tmp_path.glob("*.md"))
    assert len(produced) == 5
    assert produced[0] == "01_catalogo_e_recomendacao.md"


def test_generate_stops_on_rate_limit(tmp_path):
    factories = iter([_FakeAgent(), _FakeAgent(error_on=1)])

    code = gen.generate(agent_factory=lambda: next(factories), out_dir=tmp_path, sleep=0)
    assert code == 2
    names = {p.name for p in tmp_path.glob("*.md")}
    assert "01_catalogo_e_recomendacao.md" in names
    assert "02_promocao_e_pagamento.md" not in names


def test_generate_filter(tmp_path):
    code = gen.generate(
        agent_factory=lambda: _FakeAgent(), out_dir=tmp_path, slug_filter="03", sleep=0
    )
    assert code == 0
    names = {p.name for p in tmp_path.glob("*.md")}
    assert names == {"03_devolucao_com_confirmacao.md"}
