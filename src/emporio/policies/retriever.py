"""Busca lexical BM25 sobre os trechos do manual de políticas.

Escolha deliberada por BM25 (rank-bm25) em vez de embeddings/banco vetorial:
o manual é pequeno (~26 trechos), com vocabulário previsível e termos de
negócio recorrentes (devolução, garantia, frete, parcelamento). BM25 roda
totalmente offline, sem dependência de rede nem modelo, e o resultado é
explicável — dá para inspecionar quais tokens fizeram o match. Nesse volume,
embeddings não trariam ganho de qualidade que justifique o custo e a opacidade.
"""

import json
import re
from functools import lru_cache

from rank_bm25 import BM25Okapi

from emporio.config import get_settings
from emporio.utils import normalize

STOPWORDS = {
    "a", "o", "as", "os", "um", "uma", "uns", "umas",
    "de", "do", "da", "dos", "das", "em", "no", "na", "nos", "nas",
    "por", "para", "pra", "com", "sem", "sob", "sobre", "ao", "aos",
    "e", "ou", "mas", "que", "se", "como", "quando", "onde", "qual", "quais",
    "quanto", "quanta", "quantos", "quantas", "meu", "minha", "meus", "minhas",
    "seu", "sua", "seus", "suas", "eu", "voce", "voces", "ele", "ela", "isso",
    "este", "esta", "esse", "essa", "aquele", "aquela", "ja", "nao", "sim",
    "muito", "mais", "menos", "tem", "ter",
    "loja", "gostaria", "saber", "queria", "posso", "pode",
}

SYNONYMS = {
    "devolver": "devolucao arrependimento reembolso",
    "devolucao": "devolucao arrependimento reembolso",
    "arrependi": "arrependimento devolucao",
    "arrependimento": "arrependimento devolucao",
    "trocar": "troca",
    "troca": "troca",
    "defeito": "troca defeito",
    "estragado": "troca defeito",
    "quebrado": "troca defeito",
    "cor": "preferencia troca cor modelo tamanho",
    "modelo": "preferencia troca cor modelo tamanho",
    "parcelar": "parcelamento parcela credito",
    "parcela": "parcelamento parcela credito",
    "vezes": "parcelamento parcela",
    "pagar": "pagamento",
    "pagamento": "pagamento",
    "pix": "pix pagamento desconto",
    "abre": "horario funcionamento",
    "fecha": "horario funcionamento",
    "aberto": "horario funcionamento",
    "domingo": "horario funcionamento",
    "sabado": "horario funcionamento",
    "horario": "horario funcionamento",
    "endereco": "dados empresa endereco",
    "telefone": "dados empresa telefone whatsapp",
    "contato": "dados empresa telefone email",
    "entrega": "frete entrega prazo",
    "chega": "frete entrega prazo",
    "frete": "frete entrega prazo",
    "rastrear": "rastreamento codigo",
    "rastreio": "rastreamento codigo",
    "rastreamento": "rastreamento codigo",
    "desconto": "promocao desconto",
    "cupom": "promocao desconto",
    "promocao": "promocao desconto",
    "garantia": "garantia defeito fabricante",
    "fabricante": "garantia fabricante",
    "dados": "privacidade lgpd dados",
    "pessoais": "privacidade lgpd dados",
    "privacidade": "privacidade lgpd dados",
    "seguros": "privacidade lgpd dados",
    "acessorio": "acessorios cordas palhetas cabos",
    "acessorios": "acessorios cordas palhetas cabos",
    "corda": "acessorios cordas",
    "cordas": "acessorios cordas",
    "palheta": "acessorios cordas palhetas",
    "palhetas": "acessorios cordas palhetas",
    "amplificador": "acessorios amplificadores",
    "amplificadores": "acessorios amplificadores",
    "vendem": "acessorios comercializamos",
}


def _stem(token: str) -> str:
    return token[:5]


def tokenize(text: str) -> list[str]:
    normalized = normalize(text)
    raw_tokens = re.findall(r"[a-z0-9]+", normalized)
    tokens: list[str] = []
    for token in raw_tokens:
        if token in STOPWORDS or len(token) < 2:
            continue
        tokens.append(_stem(token))
        expansion = SYNONYMS.get(token)
        if expansion:
            for syn in expansion.split():
                tokens.append(_stem(syn))
    return tokens


class PolicyRetriever:
    def __init__(self, chunks: list[dict]):
        self._chunks = chunks
        # Repete a seção para dar mais peso ao título/caminho no ranqueamento.
        corpus = [
            tokenize(f"{chunk['section']} {chunk['section']} {chunk['text']}")
            for chunk in chunks
        ]
        self._bm25 = BM25Okapi(corpus)

    def search(self, query: str, k: int = 4) -> list[dict]:
        scores = self._bm25.get_scores(tokenize(query))
        ranked = [
            {**chunk, "score": round(float(score), 2)}
            for chunk, score in zip(self._chunks, scores, strict=True)
            if score > 0
        ]
        ranked.sort(key=lambda item: item["score"], reverse=True)
        return ranked[:k]


@lru_cache
def get_retriever() -> PolicyRetriever:
    settings = get_settings()
    path = settings.policies_json
    if not path.exists():
        raise FileNotFoundError(
            f"Índice de políticas não encontrado em {path}. "
            "Rode `python -m emporio.bootstrap` para gerar os dados."
        )
    chunks = json.loads(path.read_text(encoding="utf-8"))
    return PolicyRetriever(chunks)
