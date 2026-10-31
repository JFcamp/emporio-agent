---
inclusion: always
---

# Produto

Agente "Lia", assistente virtual da Empório da Música (Campo Grande/MS, desde 2008, slogan "Sua música começa aqui."). Atende clientes por texto: catálogo, preços, promoções, formas de pagamento, status de pedido, trocas/devoluções, garantia, frete, horários e dados da loja.

## Princípios inegociáveis

1. Nenhum preço, estoque, promoção, prazo ou status de pedido sai da "memória" do LLM. Tudo vem de ferramentas determinísticas em Python, testadas sem LLM.

2. Informação desconhecida nunca vira aprovação. Regras de devolução retornam "elegivel", "nao_elegivel" ou "precisa_confirmacao" (com a lista do que falta confirmar).

3. O desconto de 5% do PIX é calculado só no backend, a partir de produtos (id + quantidade), e nunca acumula com preço promocional. Simulação por valor livre é hipotética e não calcula PIX.

4. Pedidos só são consultados com número + e-mail ou telefone do cadastro. Telefone é comparado completo e normalizado (só dígitos, sem o 55 do país, com DDD). Pedido inexistente e contato que não confere devolvem a MESMA mensagem.

5. A loja vende só instrumentos musicais. Acessórios (cordas, palhetas, cabos, cases, pedais, amplificadores) são recusados com gentileza. Assuntos fora da loja são recusados em uma frase.

6. Reclamações, cancelamentos e casos não cobertos são encaminhados à equipe com protocolo. O agente nunca promete solução.

7. Erros técnicos nunca expõem detalhes ao cliente (sem nome de exceção). O detalhe vai para log.

## Tom (manual, seção 7.1)

Informal mas profissional, como um amigo que entende de música. Mensagens curtas de chat, valores no formato R$ 1.234,56.

## Decisões sobre os dados (suposições documentadas)

- WhatsApp oficial: (67) 3341-4444 (o manual também cita 3321-4500 uma vez).

- E-mail: contato@emporiodamusica.com.br (sem acento).

- Parcelamento (seção 3.1 prevalece sobre a tabela): 1x–3x parcela mínima R$ 50; 4x–6x mínima R$ 80; 7x–12x mínima R$ 100; até 12x sem juros. Pagamento combinado só acima de R$ 2.000.

- Disponível = status "active" E estoque > 0. Produto 96 (ativo, estoque 0) está esgotado; 136 (descontinuado) e 130 (em breve) não são vendidos, mesmo com estoque.

- Promoção vale só com is_active = 1; havendo mais de uma ativa no mesmo produto, vale o maior desconto.

- Categorias 6, 7 e 8 (sopros e cordas orquestrais) não têm produtos: informar que não há itens no momento.

- Pedidos 3 e 20 têm total diferente da soma dos itens: vale o total do pedido.

- Clientes 11 e 43 têm o mesmo e-mail: manter os dois; a verificação compara com o dono do pedido.

- estimated_delivery é PREVISÃO, nunca data de recebimento. Data de recebimento, canal (online/loja) e se o item é personalizado/"venda final" vêm do cliente.

- REFERENCE_DATE (opcional no .env) fixa a "data de hoje" para regras de prazo, porque os pedidos são de 2025/2026.
