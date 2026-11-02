"""Verificações puras dos evals (sem LLM).

check_turn recebe o que o agente devolveu num turno (texto + tool calls) e as
expectativas do caso, e retorna a lista de falhas legíveis em português. Tudo
aqui é determinístico e testável isoladamente.
"""

import re

from emporio.utils import normalize

_BRL_RE = re.compile(r"R\$(\S)")
_BRL_VALUE_RE = re.compile(r"R\$ \d{1,3}(\.\d{3})*,\d{2}")


def normalize_reply(text: str) -> str:
    # normalize() já tira acentos, baixa caixa e colapsa espaços. Trata "r$ " e
    # "r$" como equivalentes para as comparações de conteúdo.
    return normalize(text).replace("r$ ", "r$")


def subset_match(expected, actual) -> bool:
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return False
        return all(
            key in actual and subset_match(value, actual[key])
            for key, value in expected.items()
        )
    if isinstance(expected, list):
        if not isinstance(actual, list):
            return False
        return all(
            any(subset_match(item, candidate) for candidate in actual)
            for item in expected
        )
    if isinstance(expected, str) and isinstance(actual, str):
        return normalize(expected) == normalize(actual)
    return expected == actual


def brl_format_ok(text: str) -> bool:
    # Todo "R$" deve ser seguido de um espaço...
    if _BRL_RE.search(text):
        return False
    # ...e de um valor no formato 1.234,56.
    for match in re.finditer(r"R\$ \S+", text):
        token = match.group(0)
        if not _BRL_VALUE_RE.fullmatch(token.rstrip(".,;:!?)")):
            # Pode haver pontuação logo após o valor; valida o núcleo monetário.
            core = re.match(r"R\$ \d[\d.]*,\d{2}", token)
            if not core or not _BRL_VALUE_RE.fullmatch(core.group(0)):
                return False
    return True


def _tool_names(tool_calls) -> list[str]:
    return [call["name"] for call in tool_calls]


def check_turn(expect: dict, reply_text: str, tool_calls: list[dict], fallback: str) -> list[str]:
    failures: list[str] = []
    norm = normalize_reply(reply_text)
    names = _tool_names(tool_calls)

    if expect.get("no_fallback", True) and reply_text.strip() == fallback.strip():
        failures.append("resposta foi o FALLBACK")

    for tool in expect.get("tools_all", []):
        if tool not in names:
            failures.append(f"esperava chamar '{tool}' (chamou: {names or 'nenhuma'})")

    tools_any = expect.get("tools_any")
    if tools_any and not any(t in names for t in tools_any):
        failures.append(f"esperava chamar alguma de {tools_any} (chamou: {names or 'nenhuma'})")

    for tool in expect.get("tools_none", []):
        if tool in names:
            failures.append(f"não devia chamar '{tool}'")

    for rule in expect.get("args", []):
        tool, match = rule["tool"], rule["match"]
        calls = [c["args"] for c in tool_calls if c["name"] == tool]
        if not any(subset_match(match, args) for args in calls):
            failures.append(f"'{tool}' sem args esperados {match} (recebeu: {calls})")

    for rule in expect.get("args_absent", []):
        tool, keys = rule["tool"], rule["keys"]
        for call in tool_calls:
            if call["name"] != tool:
                continue
            present = [k for k in keys if call["args"].get(k) is not None]
            if present:
                failures.append(f"'{tool}' não devia ter {present} preenchido(s)")

    for needle in expect.get("contains_all", []):
        if normalize_reply(needle) not in norm:
            failures.append(f"faltou conter '{needle}'")

    contains_any = expect.get("contains_any")
    if contains_any:
        # Aceita uma lista simples (um grupo "ao menos um") ou uma lista de
        # grupos (cada grupo precisa ter ao menos um termo presente).
        groups = contains_any if contains_any and isinstance(contains_any[0], list) else [contains_any]
        for group in groups:
            if not any(normalize_reply(n) in norm for n in group):
                failures.append(f"não conteve nenhum de {group}")

    for needle in expect.get("not_contains", []):
        if normalize_reply(needle) in norm:
            failures.append(f"não devia conter '{needle}'")

    if expect.get("brl_format", True) and not brl_format_ok(reply_text):
        failures.append("formato de R$ inválido (esperado 'R$ 1.234,56')")

    return failures
