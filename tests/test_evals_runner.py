import argparse

import pytest

from emporio.agent.graph import Reply, ToolCall, classify_error
from evals import run as runner


def test_classify_error():
    class RateLimitError(Exception):
        pass

    assert classify_error(RateLimitError("boom")) == "rate_limit"
    assert classify_error(ValueError("Error code: 429 - too many")) == "rate_limit"
    assert classify_error(ValueError("conexão caiu")) == "provider"


def test_parse_retry_after():
    assert runner.parse_retry_after("Please try again in 6m17.568s. Need more") == pytest.approx(377.568)
    assert runner.parse_retry_after("try again in 41.2s") == pytest.approx(41.2)
    assert runner.parse_retry_after("try again in 1h2m3s") == 3723
    assert runner.parse_retry_after("sem padrão aqui") is None


class _ScriptedAgent:
    """Agente falso: devolve Replies roteirizadas por id de thread/turno."""

    def __init__(self, script, error_message=None):
        self._script = script
        self.last_error_message = error_message
        self._i = 0

    @staticmethod
    def new_thread_id():
        return "t"

    def chat(self, message, thread_id):
        reply = self._script[min(self._i, len(self._script) - 1)]
        self._i += 1
        return reply


def _args(**over):
    base = dict(k=None, sleep=0.0, max_wait=90.0, set="todos", rerun_failed=False,
                model=None, publish=False)
    base.update(over)
    return argparse.Namespace(**base)


def _only(monkeypatch, case_ids):
    import copy
    all_cases = runner._load_cases()
    subset = [copy.deepcopy(c) for c in all_cases if c["id"] in case_ids]
    monkeypatch.setattr(runner, "_load_cases", lambda: subset)


def test_rate_limit_short_retry_then_pass(monkeypatch):
    _only(monkeypatch, ["endereco"])
    monkeypatch.setattr(runner.time, "sleep", lambda s: None)

    attempts = {"n": 0}

    def factory():
        attempts["n"] += 1
        if attempts["n"] == 1:
            return _ScriptedAgent([Reply(runner.FALLBACK, [], error="rate_limit")],
                                  error_message="try again in 5s")
        return _ScriptedAgent([Reply("Rua 14 de Maio, 3200 — Centro", [])])

    results = runner.run_suite(_args(), agent_factory=factory)
    assert len(results) == 1
    assert results[0]["status"] == "PASS"


def test_rate_limit_long_wait_stops(monkeypatch):
    _only(monkeypatch, ["endereco", "horario_sabado"])
    monkeypatch.setattr(runner.time, "sleep", lambda s: None)

    def factory():
        return _ScriptedAgent([Reply(runner.FALLBACK, [], error="rate_limit")],
                              error_message="try again in 6m0s")

    results = runner.run_suite(_args(max_wait=90.0), agent_factory=factory)
    by_id = {r["id"]: r["status"] for r in results}
    assert by_id["endereco"] == "INFRA"
    assert by_id["horario_sabado"] == "NAO_EXECUTADO"


def test_behavior_failure(monkeypatch):
    _only(monkeypatch, ["endereco"])

    def factory():
        return _ScriptedAgent([Reply("sei lá o endereço", [])])

    results = runner.run_suite(_args(), agent_factory=factory)
    assert results[0]["status"] == "FAIL"


def test_set_holdout_only(monkeypatch):
    monkeypatch.setattr(runner.time, "sleep", lambda s: None)

    def factory():
        return _ScriptedAgent([Reply("R$ 878,40 no PIX", [
            ToolCall("simular_pagamento", {"itens": [{"produto_id": 121, "quantidade": 2}]}, "{}")
        ])])

    results = runner.run_suite(_args(set="holdout"), agent_factory=factory)
    assert results
    assert all(r["holdout"] for r in results)


def test_consolidate_results(monkeypatch, tmp_path):
    import json
    import os
    import time

    results_dir = tmp_path / "results"
    results_dir.mkdir()
    monkeypatch.setattr(runner, "RESULTS_DIR", results_dir)

    base = time.time()

    def _write(name, mtime, modelo, resultados):
        path = results_dir / name
        path.write_text(
            json.dumps({"modelo": modelo, "resultados": resultados}, ensure_ascii=False),
            encoding="utf-8",
        )
        os.utime(path, (mtime, mtime))

    # Antes do commit em src/: deve ser ignorado mesmo sendo do modelo certo.
    _write("20260101-000000.json", base - 100, "groq:m",
           [{"id": "endereco", "status": "FAIL", "holdout": False, "turns": []}])
    # Modelo diferente: ignorado.
    _write("20260102-000000.json", base + 10, "groq:outro",
           [{"id": "endereco", "status": "PASS", "holdout": False, "turns": []}])
    # Execução antiga do modelo certo: endereco FAIL.
    _write("20260103-000000.json", base + 20, "groq:m",
           [{"id": "endereco", "status": "FAIL", "holdout": False, "turns": []},
            {"id": "horario", "status": "PASS", "holdout": False, "turns": []}])
    # Execução mais recente do modelo certo: endereco agora PASS.
    _write("20260104-000000.json", base + 30, "groq:m",
           [{"id": "endereco", "status": "PASS", "holdout": False, "turns": []}])

    consolidated = runner.consolidate_results("groq:m", src_time=base)
    by_id = {r["id"]: r["status"] for r in consolidated}
    assert by_id == {"endereco": "PASS", "horario": "PASS"}  # 1 por caso, o mais novo


def test_rerun_failed_skips_passed(monkeypatch, tmp_path):
    _only(monkeypatch, ["endereco", "horario_sabado"])
    # JSON anterior: endereco PASS, horario_sabado FAIL -> só horario roda.
    import json
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    (results_dir / "20260101-000000.json").write_text(
        json.dumps({"modelo": "x", "resultados": [
            {"id": "endereco", "status": "PASS"},
            {"id": "horario_sabado", "status": "FAIL"},
        ]}, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(runner, "RESULTS_DIR", results_dir)

    seen = []

    def factory():
        return _ScriptedAgent([Reply("abre sábado até 13h", [])])

    original_run_case = runner.run_case

    def spy(case, settings, agent_factory):
        seen.append(case["id"])
        return original_run_case(case, settings, agent_factory)

    monkeypatch.setattr(runner, "run_case", spy)
    runner.run_suite(_args(rerun_failed=True), agent_factory=factory)
    assert "endereco" not in seen
    assert "horario_sabado" in seen
