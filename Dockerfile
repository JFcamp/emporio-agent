FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Metadados do pacote primeiro, para aproveitar cache de camadas.
COPY pyproject.toml README.md ./
COPY src/ ./src/
COPY data/raw/ ./data/raw/

# Instala em modo editável para que ROOT_DIR (layout src) resolva para /app,
# onde ficam data/raw e os dados gerados (data/processed, data/runtime).
RUN pip install --no-cache-dir -e .

# Gera banco e índice de políticas já na imagem, para iniciar pronto.
RUN python -m emporio.bootstrap

# Para usar Ollama rodando no host, passe
# OLLAMA_BASE_URL=http://host.docker.internal:11434
CMD ["python", "-m", "emporio.interfaces.cli"]
