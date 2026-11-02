import json

import pytest
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import ValidationError

from emporio.config import get_settings
from emporio.tools import ALL_TOOLS

EXPECTED_NAMES = [
    "buscar_produtos",
    "detalhar_produto",
    "listar_promocoes",
    "simular_pagamento",
    "consultar_pedido",
    "avaliar_troca_devolucao",
    "buscar_politica",
    "encaminhar_atendente",
]

REQUIRED = {
    "buscar_produtos": [],
    "detalhar_produto": ["nome_ou_id"],
    "listar_promocoes": [],
    "simular_pagamento": [],
    "consultar_pedido": ["numero_pedido", "email_ou_telefone"],
    "avaliar_troca_devolucao": ["numero_pedido", "email_ou_telefone", "motivo"],
    "buscar_politica": ["pergunta"],
    "encaminhar_atendente": ["motivo", "resumo"],
}


def _schema(name):
    tool = next(t for t in ALL_TOOLS if t.name == name)
    return convert_to_openai_tool(tool)["function"]


def test_all_tools_names_unique_and_complete():
    names = [t.name for t in ALL_TOOLS]
    assert names == EXPECTED_NAMES
    assert len(names) == len(set(names)) == 8


def test_descriptions_present_without_args_section():
    for tool in ALL_TOOLS:
        schema = convert_to_openai_tool(tool)["function"]
        assert schema["description"].strip()
        assert "Args:" not in schema["description"]


def test_every_argument_has_description():
    for name in EXPECTED_NAMES:
        props = _schema(name)["parameters"]["properties"]
        for arg, spec in props.items():
            assert "description" in spec, f"{name}.{arg} sem description"


@pytest.mark.parametrize("name, required", REQUIRED.items())
def test_required_arguments(name, required):
    schema_required = _schema(name)["parameters"].get("required", [])
    assert sorted(schema_required) == sorted(required)


def test_config_not_in_handoff_schema():
    props = _schema("encaminhar_atendente")["parameters"]["properties"]
    assert "config" not in props


def test_motivo_is_enum():
    props = _schema("avaliar_troca_devolucao")["parameters"]["properties"]
    assert set(props["motivo"]["enum"]) == {"arrependimento", "defeito", "preferencia"}


VALID_INVOCATIONS = {
    "buscar_produtos": {"termo": "violão"},
    "detalhar_produto": {"nome_ou_id": "95"},
    "listar_promocoes": {},
    "simular_pagamento": {"itens": [{"produto_id": 121, "quantidade": 1}]},
    "consultar_pedido": {"numero_pedido": 8, "email_ou_telefone": "x@y.com"},
    "avaliar_troca_devolucao": {
        "numero_pedido": 8,
        "email_ou_telefone": "x@y.com",
        "motivo": "defeito",
    },
    "buscar_politica": {"pergunta": "posso devolver?"},
    "encaminhar_atendente": {"motivo": "reclamacao", "resumo": "teste"},
}


@pytest.mark.parametrize("name, args", VALID_INVOCATIONS.items())
def test_invocation_returns_json_string(name, args):
    tool = next(t for t in ALL_TOOLS if t.name == name)
    output = tool.invoke(args)
    assert isinstance(output, str)
    json.loads(output)  # não lança


def test_simulate_items_pix():
    tool = next(t for t in ALL_TOOLS if t.name == "simular_pagamento")
    data = json.loads(tool.invoke({"itens": [{"produto_id": 121, "quantidade": 1}]}))
    assert data["pix"]["total"] == "R$ 439,20"
    assert data["pix"]["desconto_aplicado"] is False


def test_simulate_amount_hypothetical():
    tool = next(t for t in ALL_TOOLS if t.name == "simular_pagamento")
    data = json.loads(tool.invoke({"valor": 439.2}))
    assert data["simulacao_hipotetica"] is True


def test_handoff_uses_thread_id_from_config():
    tool = next(t for t in ALL_TOOLS if t.name == "encaminhar_atendente")
    tool.invoke(
        {"motivo": "pedido_do_cliente", "resumo": "quer falar com atendente"},
        config={"configurable": {"thread_id": "t-contrato"}},
    )
    path = get_settings().handoffs_file
    records = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert any(r.get("conversa") == "t-contrato" for r in records)


def test_invalid_motivo_fails_validation():
    tool = next(t for t in ALL_TOOLS if t.name == "avaliar_troca_devolucao")
    with pytest.raises(ValidationError):
        tool.invoke(
            {"numero_pedido": 8, "email_ou_telefone": "x@y.com", "motivo": "outro"}
        )
