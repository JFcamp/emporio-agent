---
inclusion: always
---

# Estrutura

```
data/raw/                  # originais, nunca alterados

data/processed/            # gerado pelo ETL (ignorado no git)

data/runtime/              # conversas e encaminhamentos (ignorado no git)

src/emporio/

  config.py                # Settings (.env)

  utils.py                 # normalize, only_digits, brl

  bootstrap.py             # gera banco + índice de políticas

  data/                    # etl.py, db.py

  policies/                # ingest.py, retriever.py

  domain/                  # regras puras: store.py, payments.py, returns.py

  tools/                   # lógica das ferramentas + contrato para o LLM (__init__.py)

  agent/                   # llm.py, prompts.py, graph.py

  interfaces/              # cli.py, web.py

tests/

evals/                     # cases.yaml, run.py

examples/                  # conversas reais geradas pelo agente

scripts/
```

Dependências entre camadas, sempre de cima para baixo:

interfaces → agent → tools → domain / data / policies → config / utils.

domain/ não importa banco nem LLM. Nenhuma camada de baixo importa uma de cima.
