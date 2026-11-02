# Conversas de exemplo

Estas conversas são geradas pelo **agente real** (não são roteiros fixos) com:

```
make examples
```

Cada turno mostra a mensagem do cliente e a resposta da Lia. Os blocos
"Ferramentas consultadas" revelam exatamente quais ferramentas o agente chamou
e com quais argumentos — é assim que se vê que preços, estoque, promoções e
status de pedido vêm do backend, nunca da "memória" do modelo.

A **data de referência é 20/02/2026**: os pedidos de teste são de 2025/2026, e
fixar a data torna os prazos (devolução, garantia) e o status de aberto/fechado
reproduzíveis entre gerações.

| Arquivo | Cenário | O que demonstra |
| --- | --- | --- |
| [01_catalogo_e_recomendacao.md](01_catalogo_e_recomendacao.md) | Catálogo e recomendação | Busca com filtro de preço, recomendação para iniciante e cálculo de PIX |
| [02_promocao_e_pagamento.md](02_promocao_e_pagamento.md) | Promoção e pagamento | Promoção ativa, PIX sem desconto extra e parcelamento máximo sem juros |
| [03_devolucao_com_confirmacao.md](03_devolucao_com_confirmacao.md) | Devolução com confirmação de dados | Identificação do pedido, perguntas sobre o que falta e aplicação do prazo |
| [04_pedido_lgpd_e_reclamacao.md](04_pedido_lgpd_e_reclamacao.md) | Pedido, proteção de dados e reclamação | Status só após verificar o contato e encaminhamento com protocolo |
| [05_escopo_e_seguranca.md](05_escopo_e_seguranca.md) | Escopo e segurança | Recusa de acessórios, categoria sem produtos, injeção de prompt e dados da loja |
