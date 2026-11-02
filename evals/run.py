"""Runner dos evals contra o agente REAL (usa o LLM configurado).

Para cada caso: fixa reference_date, abre uma thread nova, roda os turnos e
aplica as verificações de checks.py. Falhas de infraestrutura (limite do
provedor) são separadas das falhas de comportamento: só estas reprovam a suíte.
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
from evals.checks import check_turn

CASES_PATH = Path(__file__).parent / "cases.yaml"
RESULTS_DIR = Path(__file__).parent / "results"
DEFAULT_REFERENCE_DATE = "2026-02-20"
_RATE_LIMIT_RE = re.compile(r"429|rate limit", re.IGNORECASE)


def _load_cases() -> list[dict]:
    return yaml.safe_load(CASES_PATH.read_text(encoding="utf-8"))


def _log_has_rate_limit_since(log_path: Path, size_before: int) -> bool:
    if not log_path.exists():
        return False
    with log_path.open("r", encoding="utf-8", errors="ignore") as handle:
        handle.seek(size_before)
        return bool(_RATE_LIMIT_RE.search(handle.read()))


def _log_size(log_path: Path) -> int:
    return log_path.stat().st_size if log_path.exists() else 0


def run_case(case: dict, settings, log_path: Path, sleep: float) -> dict:
    reference = case.get("reference_date", DEFAULT_REFERENCE_DATE)
    settings.reference_date = date.fromisoformat(reference)

    agent = EmporioAgent(persist=False)
    thread_id = agent.new_thread_id()

    turns_result = []
    behavior_failures = 0
    infra = False

    for index, turn in enumerate(case["turns"]):
        if index > 0 and sleep:
            time.sleep(sleep)

        size_before = _log_size(log_path)
        started = time.monotonic()
        reply = agent.chat(turn["user"], thread_id)
        elapsed = round(time.monotonic() - started, 2)

        tool_calls = [{"name": c.name, "args": c.args} for c in reply.tool_calls]
        failures = check_turn(turn.get("expect", {}), reply.text, tool_calls, FALLBACK)

        turn_infra = False
        if reply.text.strip() == FALLBACK.strip() and _log_has_rate_limit_since(
            log_path, size_before
        ):
            turn_infra = True
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
                "seconds": elapsed,
            }
        )

    if infra:
        status = "INFRA"
    elif behavior_failures:
        status = "FAIL"
    else:
        status = "PASS"

    return {
        "id": case["id"],
        "descricao": case.get("descricao", ""),
        "reference_date": reference,
        "status": status,
        "turns": turns_result,
    }


def _tools_summary(turns: list[dict]) -> str:
    parts = []
    for turn in turns:
        names = ", ".join(c["name"] for c in turn["tools"]) or "—"
        parts.append(names)
    return " | ".join(parts)


def _failures_summary(turns: list[dict]) -> str:
    flat = [f for turn in turns for f in turn["failures"]]
    return "; ".join(flat) if flat else "—"


def _render_markdown(results: list[dict], model: str) -> str:
    total = len(results)
    passed = sum(1 for r in results if r["status"] == "PASS")
    behavior = sum(1 for r in results if r["status"] == "FAIL")
    infra = sum(1 for r in results if r["status"] == "INFRA")
    now = datetime.now(STORE_TZ).strftime("%d/%m/%Y %H:%M")

    lines = [
        "# Avaliação do agente",
        "",
        f"- Modelo: {model}",
        f"- Data: {now}",
        f"- Total: {total}",
        f"- Aprovados: {passed}",
        f"- Falhas de comportamento: {behavior}",
        f"- Falhas de infra (provedor): {infra}",
        "",
        "| Caso | Resultado | Falhas | Ferramentas por turno | Tempo (s) |",
        "| --- | --- | --- | --- | --- |",
    ]
    for r in results:
        seconds = round(sum(t["seconds"] for t in r["turns"]), 2)
        lines.append(
            f"| {r['id']} | {r['status']} | {_failures_summary(r['turns'])} | "
            f"{_tools_summary(r['turns'])} | {seconds} |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Roda os evals contra o agente real")
    parser.add_argument("-k", help="filtra por id (vários separados por vírgula)")
    parser.add_argument("--sleep", type=float, default=3.0, help="pausa entre turnos (s)")
    parser.add_argument("--publish", action="store_true", help="também grava evals/REPORT.md")
    args = parser.parse_args()

    settings = get_settings()
    original_reference = settings.reference_date
    log_path = settings.runtime_dir / "emporio.log"

    cases = _load_cases()
    if args.k:
        wanted = {k.strip() for k in args.k.split(",")}
        cases = [c for c in cases if c["id"] in wanted]

    model = describe()
    results = []
    try:
        for case in cases:
            result = run_case(case, settings, log_path, args.sleep)
            results.append(result)
            print(f"[{result['status']}] {result['id']}")
    finally:
        settings.reference_date = original_reference

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

    behavior_failures = sum(1 for r in results if r["status"] == "FAIL")
    infra_failures = sum(1 for r in results if r["status"] == "INFRA")
    print(
        f"\nTotal: {len(results)} | comportamento: {behavior_failures} | infra: {infra_failures}"
    )
    if behavior_failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
