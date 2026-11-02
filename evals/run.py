"""Runner dos evals contra o agente REAL (usa o LLM configurado).

Para cada caso: fixa reference_date, abre uma thread nova, roda os turnos e
aplica as verificações de checks.py. Falhas de infraestrutura (limite do
provedor) são separadas das de comportamento: só estas reprovam a suíte.

Resiliência ao limite do provedor: quando um turno cai em FALLBACK por
rate_limit, o caso é marcado INFRA. Se o provedor sugerir uma espera curta
(<= --max-wait), o runner espera e refaz o caso; se sugerir uma espera longa
(limite diário), para e marca os casos restantes como NAO_EXECUTADO.
"""

import argparse
import json
import re
import time
from datetime import date, datetime
from pathlib import Path

import yaml

from emporio.agent.graph import FALLBACK, EmporioAgent
from emporio.agent.llm import describe
from emporio.config import STORE_TZ, get_settings
from emporio.interfaces.common import setup_logging
from evals.checks import check_turn

CASES_PATH = Path(__file__).parent / "cases.yaml"
RESULTS_DIR = Path(__file__).parent / "results"
DEFAULT_REFERENCE_DATE = "2026-02-20"
MAX_ATTEMPTS = 2

_RETRY_RE = re.compile(
    r"try again in\s+(?:(\d+)h)?(?:(\d+)m)?(?:(\d+(?:\.\d+)?)s)?", re.IGNORECASE
)


def _load_cases() -> list[dict]:
    return yaml.safe_load(CASES_PATH.read_text(encoding="utf-8"))


def parse_retry_after(message: str | None) -> float | None:
    if not message:
        return None
    match = _RETRY_RE.search(message)
    if not match or not any(match.groups()):
        return None
    hours, minutes, seconds = match.groups()
    total = 0.0
    if hours:
        total += int(hours) * 3600
    if minutes:
        total += int(minutes) * 60
    if seconds:
        total += float(seconds)
    return total


def _default_factory() -> EmporioAgent:
    return EmporioAgent(persist=False)


def run_case(case: dict, settings, agent_factory) -> tuple[dict, EmporioAgent]:
    reference = case.get("reference_date", DEFAULT_REFERENCE_DATE)
    settings.reference_date = date.fromisoformat(reference)

    agent = agent_factory()
    thread_id = agent.new_thread_id()

    turns_result = []
    behavior_failures = 0
    infra = False

    for turn in case["turns"]:
        started = time.monotonic()
        reply = agent.chat(turn["user"], thread_id)
        elapsed = round(time.monotonic() - started, 2)

        tool_calls = [{"name": c.name, "args": c.args} for c in reply.tool_calls]
        failures = check_turn(turn.get("expect", {}), reply.text, tool_calls, FALLBACK)

        turn_infra = reply.error is not None
        if turn_infra:
            infra = True
        elif failures:
            behavior_failures += len(failures)

        turns_result.append(
            {
                "user": turn["user"],
                "tools": tool_calls,
                "reply": reply.text,
                "failures": failures,
                "infra": turn_infra,
                "error": reply.error,
                "seconds": elapsed,
            }
        )
        if turn_infra:
            break  # não adianta seguir o roteiro depois de um erro de provedor

    if infra:
        status = "INFRA"
    elif behavior_failures:
        status = "FAIL"
    else:
        status = "PASS"

    result = {
        "id": case["id"],
        "descricao": case.get("descricao", ""),
        "reference_date": reference,
        "holdout": bool(case.get("holdout", False)),
        "status": status,
        "turns": turns_result,
    }
    return result, agent


def _tools_summary(turns: list[dict]) -> str:
    return " | ".join(", ".join(c["name"] for c in t["tools"]) or "—" for t in turns)


def _failures_summary(turns: list[dict]) -> str:
    flat = [f for turn in turns for f in turn["failures"]]
    return "; ".join(flat) if flat else "—"


def _counts(rows: list[dict]) -> dict:
    return {
        status: sum(1 for r in rows if r["status"] == status)
        for status in ("PASS", "FAIL", "INFRA", "NAO_EXECUTADO")
    }


def _block(title: str, rows: list[dict], conjunto: str) -> list[str]:
    c = _counts(rows)
    lines = [
        f"## {title} ({c['PASS']}/{len(rows)} aprovados · "
        f"{c['FAIL']} comportamento · {c['INFRA']} infra · {c['NAO_EXECUTADO']} não executados)",
        "",
        "| Caso | Conjunto | Resultado | Falhas | Ferramentas por turno | Tempo (s) |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for r in rows:
        seconds = round(sum(t["seconds"] for t in r["turns"]), 2)
        lines.append(
            f"| {r['id']} | {conjunto} | {r['status']} | {_failures_summary(r['turns'])} | "
            f"{_tools_summary(r['turns'])} | {seconds} |"
        )
    lines.append("")
    return lines


def _render_markdown(results: list[dict], model: str) -> str:
    c = _counts(results)
    now = datetime.now(STORE_TZ).strftime("%d/%m/%Y %H:%M")
    tuning = [r for r in results if not r["holdout"]]
    holdout = [r for r in results if r["holdout"]]

    lines = [
        "# Avaliação do agente",
        "",
        f"- Modelo: {model}",
        f"- Data: {now}",
        f"- Total: {len(results)}",
        f"- Aprovados: {c['PASS']}",
        f"- Falhas de comportamento: {c['FAIL']}",
        f"- Falhas de infra (provedor): {c['INFRA']}",
        f"- Não executados: {c['NAO_EXECUTADO']}",
        "",
    ]
    if tuning:
        lines += _block("Casos de ajuste", tuning, "ajuste")
    if holdout:
        lines += _block("Casos de validação (holdout)", holdout, "holdout")
    return "\n".join(lines) + "\n"


def _not_executed(case: dict) -> dict:
    return {
        "id": case["id"],
        "descricao": case.get("descricao", ""),
        "reference_date": case.get("reference_date", DEFAULT_REFERENCE_DATE),
        "holdout": bool(case.get("holdout", False)),
        "status": "NAO_EXECUTADO",
        "turns": [],
    }


def _latest_statuses() -> dict[str, str]:
    files = sorted(RESULTS_DIR.glob("2*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    statuses: dict[str, str] = {}
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        for result in data["resultados"]:
            statuses.setdefault(result["id"], result["status"])
    return statuses


def _select_cases(cases: list[dict], args) -> list[dict]:
    if args.k:
        wanted = {k.strip() for k in args.k.split(",")}
        cases = [c for c in cases if c["id"] in wanted]
    if args.set == "ajuste":
        cases = [c for c in cases if not c.get("holdout")]
    elif args.set == "holdout":
        cases = [c for c in cases if c.get("holdout")]
    if args.rerun_failed:
        previous = _latest_statuses()
        cases = [c for c in cases if previous.get(c["id"]) != "PASS"]
    return cases


def run_suite(args, agent_factory=_default_factory) -> list[dict]:
    settings = get_settings()
    original_reference = settings.reference_date
    cases = _select_cases(_load_cases(), args)

    results: list[dict] = []
    stopped_at: int | None = None
    try:
        for index, case in enumerate(cases):
            result, agent = run_case(case, settings, agent_factory)
            attempts = 1

            # Enquanto for rate_limit: espera curta -> refaz o caso; espera
            # longa (limite diário) -> para a execução.
            while result["status"] == "INFRA" and _is_rate_limit(result):
                wait = parse_retry_after(agent.last_error_message)
                if (wait is not None and wait > args.max_wait) or attempts >= MAX_ATTEMPTS:
                    if wait is not None and wait > args.max_wait:
                        stopped_at = index
                    break
                time.sleep((wait or 0) + 2)
                result, agent = run_case(case, settings, agent_factory)
                attempts += 1

            results.append(result)
            print(f"[{result['status']}] {result['id']}")
            if stopped_at is not None:
                break
    finally:
        settings.reference_date = original_reference

    if stopped_at is not None:
        for case in cases[stopped_at + 1:]:
            results.append(_not_executed(case))
            print(f"[NAO_EXECUTADO] {case['id']}")

    return results


def _is_rate_limit(result: dict) -> bool:
    return any(t.get("error") == "rate_limit" for t in result["turns"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Roda os evals contra o agente real")
    parser.add_argument("-k", help="filtra por id (vários separados por vírgula)")
    parser.add_argument("--sleep", type=float, default=3.0, help="(mantido por compat.)")
    parser.add_argument("--max-wait", type=float, default=90.0, help="espera máxima por retry (s)")
    parser.add_argument(
        "--set", choices=["ajuste", "holdout", "todos"], default="todos", help="qual conjunto"
    )
    parser.add_argument("--rerun-failed", action="store_true", help="só casos não-PASS anteriores")
    parser.add_argument("--model", help="sobrescreve o modelo Groq só nesta execução")
    parser.add_argument("--publish", action="store_true", help="também grava evals/REPORT.md")
    args = parser.parse_args()

    setup_logging()
    settings = get_settings()
    if args.model:
        settings.groq_model = args.model
    model = describe() if not args.model else f"groq:{args.model}"

    results = run_suite(args)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(STORE_TZ).strftime("%Y%m%d-%H%M%S")
    (RESULTS_DIR / f"{timestamp}.json").write_text(
        json.dumps({"modelo": model, "resultados": results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    markdown = _render_markdown(results, model)
    (RESULTS_DIR / "latest.md").write_text(markdown, encoding="utf-8")
    if args.publish:
        (Path(__file__).parent / "REPORT.md").write_text(markdown, encoding="utf-8")

    c = _counts(results)
    print(
        f"\nTotal: {len(results)} | PASS: {c['PASS']} | comportamento: {c['FAIL']} | "
        f"infra: {c['INFRA']} | não executados: {c['NAO_EXECUTADO']}"
    )
    if c["FAIL"]:
        raise SystemExit(1)
    if c["INFRA"] or c["NAO_EXECUTADO"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
