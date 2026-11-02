.PHONY: help install setup chat web test lint evals examples docker-build docker-chat

help:  ## Lista os alvos disponíveis
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "} {printf "  %-14s %s\n", $$1, $$2}'

install:  ## Instala o pacote em modo editável com extras de dev e web
	pip install -e ".[dev,web]"

setup:  ## Gera o banco e o índice de políticas
	python -m emporio.bootstrap

chat:  ## Abre o atendimento no terminal (CLI)
	python -m emporio.interfaces.cli

web:  ## Abre a interface web (Streamlit)
	streamlit run src/emporio/interfaces/web.py

test:  ## Roda os testes
	pytest -q

lint:  ## Checa o estilo com ruff
	ruff check .

evals:  ## Roda os evals determinísticos
	python -m evals.run

examples:  ## Gera conversas de exemplo
	python scripts/generate_examples.py

docker-build:  ## Constrói a imagem Docker
	docker build -t emporio-agent .

docker-chat:  ## Abre a CLI dentro do container
	docker run --rm -it --env-file .env emporio-agent
