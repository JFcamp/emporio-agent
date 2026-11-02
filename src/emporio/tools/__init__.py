"""Contrato das ferramentas que o LLM enxerga.

Esta camada só define nome, descrição e argumentos visíveis ao LLM, chama a
lógica em catalog.py / orders.py / support.py e serializa a saída em JSON.
Nenhuma regra de negócio vive aqui. As docstrings (estilo Google, em português)
fazem parte do prompt e são escritas pensando no modelo.
"""

import json
from typing import Literal

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from emporio.tools import catalog, orders, support


def _out(data) -> str:
    return json.dumps(data, ensure_ascii=False)


class ItemCompra(BaseModel):
    """Item de uma simulação de compra."""

    produto_id: int = Field(description="ID do produto no catálogo.")
    quantidade: int = Field(default=1, ge=1, description="Quantidade desejada (mínimo 1).")


@tool(parse_docstring=True)
def buscar_produtos(
    termo: str | None = None,
    categoria: str | None = None,
    preco_max: float | None = None,
    preco_min: float | None = None,
    apenas_disponiveis: bool = True,
) -> str:
    """Busca instrumentos no catálogo com filtros.

    Use para perguntas abertas como "violões até R$ 1000" ou "guitarras Fender".
    Os preços retornados já consideram as promoções ativas.

    Args:
        termo: Palavras do cliente para buscar por nome, características ou marca.
        categoria: Categoria desejada (ex.: "violões", "guitarras", "ukuleles").
        preco_max: Preço máximo em reais, aplicado ao preço final (com promoção).
        preco_min: Preço mínimo em reais, aplicado ao preço final (com promoção).
        apenas_disponiveis: Se verdadeiro, lista só o que está em estoque para compra.
    """
    return _out(
        catalog.search_products(
            term=termo,
            category=categoria,
            max_price=preco_max,
            min_price=preco_min,
            only_available=apenas_disponiveis,
        )
    )


@tool(parse_docstring=True)
def detalhar_produto(nome_ou_id: str) -> str:
    """Mostra preço, promoção, disponibilidade e especificações de UM produto.

    Use quando o cliente cita um produto específico. Se o produto estiver
    indisponível, traz alternativas. Se a resposta vier com "candidatos",
    confirme com o cliente qual deles é antes de seguir.

    Args:
        nome_ou_id: Nome do produto ou o número do ID citado pelo cliente.
    """
    return _out(catalog.get_product_details(nome_ou_id))


@tool(parse_docstring=True)
def listar_promocoes() -> str:
    """Lista as promoções ativas agora.

    Mostra o preço original, o desconto e o preço final de cada produto em
    promoção no momento.
    """
    return _out(catalog.list_active_promotions())


@tool(parse_docstring=True)
def simular_pagamento(
    itens: list[ItemCompra] | None = None,
    valor: float | None = None,
    parcelas: int | None = None,
) -> str:
    """Simula formas de pagamento: PIX, débito, boleto e crédito.

    Para produtos, SEMPRE use "itens" (id e quantidade): preço, promoção e o
    desconto do PIX são calculados pelo sistema. NUNCA passe em "valor" um preço
    lido de outra ferramenta. Use "valor" apenas para um valor avulso citado
    pelo cliente; nesse caso o desconto do PIX não é calculado.

    Args:
        itens: Lista de itens da compra, cada um com produto_id e quantidade.
        valor: Valor avulso em reais, só para simulação hipotética sem PIX.
        parcelas: Número de parcelas no crédito a verificar (1 a 12).
    """
    item_dicts = (
        [{"produto_id": i.produto_id, "quantidade": i.quantidade} for i in itens]
        if itens
        else None
    )
    return _out(
        support.simulate_payment(items=item_dicts, amount=valor, installments=parcelas)
    )


@tool(parse_docstring=True)
def consultar_pedido(numero_pedido: int, email_ou_telefone: str) -> str:
    """Consulta status, itens, rastreio e previsão de entrega de um pedido.

    Exige o número do pedido E o e-mail ou telefone (com DDD) usado na compra.
    Se o cliente não informou os dois, peça antes de chamar. Se a resposta vier
    com "verificado": false, não dê nenhuma informação sobre o pedido.

    Args:
        numero_pedido: Número do pedido informado pelo cliente.
        email_ou_telefone: E-mail ou telefone com DDD usado na compra.
    """
    return _out(orders.get_order_status(numero_pedido, email_ou_telefone))


@tool(parse_docstring=True)
def avaliar_troca_devolucao(
    numero_pedido: int,
    email_ou_telefone: str,
    motivo: Literal["arrependimento", "defeito", "preferencia"],
    data_recebimento: str | None = None,
    compra_online: bool | None = None,
    item_personalizado_ou_venda_final: bool | None = None,
) -> str:
    """Avalia troca ou devolução aplicando os prazos da política.

    Retorna "elegivel", "nao_elegivel" ou "precisa_confirmacao". Preencha os
    campos opcionais SOMENTE com o que o cliente disse explicitamente; nunca
    deduza a data de recebimento a partir da previsão de entrega. Quando vier
    "precisa_confirmacao", faça ao cliente as perguntas de "falta_confirmar" e
    chame de novo com as respostas.

    Args:
        numero_pedido: Número do pedido informado pelo cliente.
        email_ou_telefone: E-mail ou telefone com DDD usado na compra.
        motivo: Motivo da solicitação: arrependimento, defeito ou preferencia.
        data_recebimento: Data em que o cliente recebeu o produto (AAAA-MM-DD).
        compra_online: Verdadeiro se a compra foi online; falso se na loja física.
        item_personalizado_ou_venda_final: Verdadeiro se o item teve
            personalização/ajuste sob encomenda ou foi de liquidação "venda final".
    """
    return _out(
        orders.evaluate_return(
            order_id=numero_pedido,
            contact=email_ou_telefone,
            reason=motivo,
            received_date=data_recebimento,
            online_purchase=compra_online,
            special_item=item_personalizado_ou_venda_final,
        )
    )


@tool(parse_docstring=True)
def buscar_politica(pergunta: str) -> str:
    """Consulta o manual de políticas da loja.

    Cobre trocas, garantia, frete, pagamento, promoções, LGPD e o que a loja
    vende ou não. Escreva a pergunta com as palavras do cliente.

    Args:
        pergunta: A dúvida do cliente, nas palavras dele.
    """
    return _out(support.search_policies(pergunta))


@tool(parse_docstring=True)
def encaminhar_atendente(
    motivo: Literal["reclamacao", "cancelamento", "caso_nao_coberto", "pedido_do_cliente"],
    resumo: str,
    contato_cliente: str | None = None,
    config: RunnableConfig = None,
) -> str:
    """Registra o caso para a equipe humana e devolve protocolo e prazo.

    Use para reclamações, cancelamentos, pedido do cliente para falar com uma
    pessoa ou casos que as políticas não cobrem. Nunca prometa solução.

    Args:
        motivo: Tipo do encaminhamento.
        resumo: Resumo objetivo do caso para a equipe.
        contato_cliente: E-mail ou telefone do cliente, se informado.
    """
    thread_id = None
    if config and "configurable" in config:
        thread_id = config["configurable"].get("thread_id")
    return _out(
        support.handoff_to_human(
            reason=motivo,
            summary=resumo,
            customer_contact=contato_cliente,
            thread_id=thread_id,
        )
    )


ALL_TOOLS = [
    buscar_produtos,
    detalhar_produto,
    listar_promocoes,
    simular_pagamento,
    consultar_pedido,
    avaliar_troca_devolucao,
    buscar_politica,
    encaminhar_atendente,
]
