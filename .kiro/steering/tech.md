---
inclusion: always
---

# Tecnologia

- Python 3.11+. Pacote instalável em src/emporio (layout src), configurado em pyproject.toml.

- Agente: LangGraph (grafo explícito: nó do modelo + ToolNode + aresta condicional) com checkpointer SQLite para histórico por thread_id.

- LLM gratuito e configurável por .env: Groq (padrão, modelo openai/gpt-oss-120b) via langchain-groq, ou Ollama local (qwen3:8b, reasoning desligado) via langchain-ollama.

- Dados: CSVs carregados por ETL em SQLite (sqlite3 da stdlib), view v_catalog com as regras de disponibilidade e promoção. Ferramentas usam SQL parametrizado e abrem o banco em modo somente leitura. Nada de text-to-SQL.

- Manual de políticas: PDF extraído com pypdfium2, dividido por seção numerada, busca BM25 (rank-bm25). Sem embeddings e sem banco vetorial.

- Busca de produtos: rapidfuzz para categoria e nomes.

- Interfaces: CLI com rich (principal) e Streamlit (secundária). Ambas usam a mesma classe de fachada do agente.

- Testes: pytest, sem rede e sem LLM real (usar modelo falso nos testes do grafo). Lint: ruff (line-length 110).

- Avaliação do agente real: evals determinísticos em YAML, verificados por turno.

- Dinheiro: cálculos em centavos inteiros; parcelas fecham o total ajustando a última.

- Não adicione dependências fora da lista do pyproject sem perguntar.

- Fine-tuning está fora do escopo (dados mudam e precisam vir do sistema em tempo real).

## Convenções

- Código, nomes de funções e variáveis em inglês. Textos para o usuário, docstrings das ferramentas do LLM, nomes das ferramentas e README em português do Brasil.

- Funções pequenas, com type hints. Sem comentários óbvios; comente apenas decisões de negócio.

- Toda etapa termina com `pytest -q` e `ruff check .` passando, e um commit em Conventional Commits (feat, fix, test, docs, chore).
