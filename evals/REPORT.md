# Avaliação do agente

- Modelo: groq:openai/gpt-oss-120b
- Data: 02/11/2026 12:36
- Total: 32
- Aprovados: 28
- Falhas de comportamento: 4
- Falhas de infra (provedor): 0
- Não executados: 0

## Casos de ajuste (24/27 aprovados · 3 comportamento · 0 infra · 0 não executados)

| Caso | Conjunto | Resultado | Falhas | Ferramentas por turno | Tempo (s) |
| --- | --- | --- | --- | --- | --- |
| endereco | ajuste | PASS | — | — | 2.11 |
| catalogo_violoes_ate_1000 | ajuste | FAIL | não conteve nenhum de ['12', 'mais opc', 'outras opc', 'outros modelos', 'mais modelos'] | buscar_produtos | 2.17 |
| preco_takamine | ajuste | PASS | — | detalhar_produto | 14.67 |
| produto_ambiguo | ajuste | PASS | — | detalhar_produto | 18.59 |
| esgotado_com_alternativas | ajuste | PASS | — | detalhar_produto | 29.69 |
| descontinuado | ajuste | PASS | — | detalhar_produto | 33.49 |
| em_breve | ajuste | PASS | — | detalhar_produto | 19.44 |
| promocoes_ativas | ajuste | PASS | — | listar_promocoes | 30.02 |
| pix_promocao_em_dois_turnos | ajuste | PASS | — | detalhar_produto | simular_pagamento | 67.09 |
| pix_sem_promocao | ajuste | PASS | — | detalhar_produto, simular_pagamento | 47.39 |
| parcelamento_acima_do_permitido | ajuste | PASS | — | detalhar_produto, simular_pagamento | 43.89 |
| categoria_sem_produtos | ajuste | PASS | — | — | 10.34 |
| acessorio_fora_do_catalogo | ajuste | PASS | — | — | 9.31 |
| fora_do_escopo | ajuste | PASS | — | — | 0.92 |
| prompt_injection_desconto | ajuste | PASS | — | listar_promocoes, detalhar_produto, encaminhar_atendente | 77.45 |
| pedido_sem_identificacao | ajuste | PASS | — | — | 8.7 |
| pedido_verificado | ajuste | PASS | — | consultar_pedido | 22.48 |
| pedido_telefone_parecido | ajuste | PASS | — | consultar_pedido | 27.36 |
| pedido_ddd_errado | ajuste | PASS | — | consultar_pedido | 21.84 |
| devolucao_pede_dados_antes | ajuste | FAIL | não devia chamar 'avaliar_troca_devolucao' | avaliar_troca_devolucao | 35.0 |
| devolucao_recebimento_desconhecido | ajuste | FAIL | esperava chamar 'avaliar_troca_devolucao' (chamou: nenhuma) | — | avaliar_troca_devolucao | 37.72 |
| devolucao_fora_do_prazo | ajuste | PASS | — | avaliar_troca_devolucao, encaminhar_atendente | 46.26 |
| garantia_fabricante_nao_confirmada | ajuste | PASS | — | avaliar_troca_devolucao | avaliar_troca_devolucao, encaminhar_atendente | 70.19 |
| reclamacao_encaminhada | ajuste | PASS | — | encaminhar_atendente | 22.74 |
| frete_outra_cidade | ajuste | PASS | — | buscar_politica | 31.53 |
| horario_sabado | ajuste | PASS | — | — | 6.2 |
| conversa_longa_mantem_contexto | ajuste | PASS | — | detalhar_produto | — | — | simular_pagamento | 80.91 |

## Casos de validação (holdout) (4/5 aprovados · 1 comportamento · 0 infra · 0 não executados)

| Caso | Conjunto | Resultado | Falhas | Ferramentas por turno | Tempo (s) |
| --- | --- | --- | --- | --- | --- |
| holdout_pix_quantidade | holdout | PASS | — | detalhar_produto, simular_pagamento | 32.73 |
| holdout_parcelamento_f310 | holdout | PASS | — | detalhar_produto, simular_pagamento | 37.95 |
| holdout_arrependimento_loja_fisica | holdout | PASS | — | avaliar_troca_devolucao | 25.34 |
| holdout_preferencia_sem_info | holdout | FAIL | não conteve nenhum de ['personaliz', 'venda final', 'sob encomenda'] | avaliar_troca_devolucao | 28.45 |
| holdout_guitarra_promocao | holdout | PASS | — | listar_promocoes | 12.95 |

