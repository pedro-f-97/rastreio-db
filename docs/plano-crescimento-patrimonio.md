# Plano: quanto o património cresce por mês

Estado: **aprovado** (23/10/2026).

## 1. O problema

A página Património mostra o valor no fim de cada mês num gráfico, mas não diz
quanto cresce por mês, nem quanto desse crescimento vem do que se poupa e quanto
vem da valorização dos investimentos e dos bens.

## 2. Decisões já tomadas (23/10/2026)

1. **Tendência (B).** O crescimento por mês é a inclinação da recta dos mínimos
   quadrados ajustada ao património no fim de cada mês, e não
   (último − primeiro) ÷ meses. Usa todos os meses, por isso um mês fora do
   normal pesa pouco, e os saltos de preço (registados de vez em quando) ficam
   repartidos.
2. **Separado por origem, de forma direta (D2).**
   - Valorização acumulada num fim de mês = soma, por ativo, de
     `valor − custo_base + realizado`, com os mesmos cálculos que o Património
     já faz (`_resumo_valor_ativo`: FIFO com unidades, custo acumulado sem
     unidades). O `realizado` inclui as mais-valias das vendas e os dividendos
     registados como movimento, para o ganho não desaparecer quando a venda o
     passa para a liquidez.
   - Do que poupas = o resto: património − valorização acumulada.
   - As duas tendências somam a do total (a recta é linear nos valores).
   - Comprar um bem ou um investimento não muda nada: a liquidez desce e o ativo
     sobe pelo custo. O carro entra só pela desvalorização, quando se regista um
     preço novo.
3. **Sem o mês em curso**, que está incompleto.
4. **Acompanha o filtro de ano** do gráfico (Todos / cada ano).

## 3. Decisões tomadas sobre o ecrã (23/10/2026)

5. **Mínimo de 3 meses.** Com menos de 3 meses completos no período, o cartão
   mostra «Poucos meses para calcular a tendência» em vez dos valores.
6. **Por cima do gráfico «Evolução»**, com o mesmo filtro de ano:

   > Cresce **X €/mês** · do que poupas **Y €/mês** · da valorização **Z €/mês**
   > Tendência de N meses, de mm/aaaa a mm/aaaa, sem o mês em curso.

## 4. Passos (service → router → api → página)

### 4.1 Serviço (`backend/servicos/patrimonio_serv.py`)

- `calcular_patrimonio_em` e `gerar_evolucao` recebem `com_valorizacao=False`;
  com `True`, o ponto traz também `valorizacao` (a soma do ponto 2, arredondada
  ao cêntimo). O `/evolucao` fica como está.
- Função nova `calcular_crescimento(db, ano, hoje)`:
  - Período: do mês da primeira transação (ou de janeiro de `ano`) até ao fim
    do último mês completo antes de `hoje` (ou dezembro de `ano`).
  - Pontos de `gerar_evolucao` nesse período.
  - Inclinação `Σ(x−x̄)(y−ȳ) / Σ(x−x̄)²`, com `x` = índice do mês, para o total
    e para a valorização. Do que poupas = total − valorização, já arredondados,
    para as parcelas somarem o total ao cêntimo.
  - Devolve `{de, ate, meses, total, poupanca, valorizacao}`, com os três
    valores a `null` abaixo do mínimo de meses.
- Sem modelo novo nem migração.

### 4.2 Router (`backend/routers/patrimonio.py`)

- `GET /api/patrimonio/crescimento?ano=2025` (`ano` omitido = todos), com
  `date.today()` como `hoje`.

### 4.3 Frontend

- `frontend/src/api/patrimonio.js`: `obterCrescimento(ano)`.
- `pages/Patrimonio.jsx`: o cartão do ponto 6, pedido de novo quando muda o
  filtro de ano. Reutilizar as classes `cartao` de `componentes.css`.

### 4.4 Documentação

- README, «Decisões de design»: a tendência, a separação direta e o mês em
  curso de fora.
- Página Conceitos, secção Património: um parágrafo sobre o crescimento.

### 4.5 Testes (`backend/tests/test_crescimento_patrimonio.py`)

Valores escritos à mão, com a conta no comentário, e `hoje` fixo:

- só poupança: +100 €/mês numa conta dá total 100, poupança 100, valorização 0;
- tendência e não média: meses 0, 100, 100, 400 dão 120 €/mês (e não 133,33);
- comprar um ETF não muda nada; o preço sobe 50 € num mês: entra na valorização;
- vender com mais-valia: a valorização acumulada não cai ao vender;
- um bem que desvaloriza: valorização negativa;
- o mês em curso fica de fora; o filtro de ano corta o período;
- abaixo do mínimo de meses, os valores vêm a `null`;
- as parcelas somam o total ao cêntimo;
- a API devolve o mesmo que o serviço.

Verificar os testes novos por mutação numa cópia em `/tmp` (ver `AGENTS.md`).

## 5. Verificação com os dados reais (numa cópia)

Fica do lado do utilizador. Atenção: o preço do USDC (1,28 €) está errado e
distorce a valorização até ser corrigido.

## 6. Fora do âmbito (ficam registados, não se tratam aqui)

- Uma compra de investimento ainda por tratar (pendente) tira dinheiro da
  liquidez sem ativo do outro lado, e conta como «menos poupança» até ser
  tratada.
- Um dividendo que entra só como transação, sem movimento no ativo, conta como
  poupança e não como valorização.
- Contas sem extracto importado em parte do período: o saldo fica parado e a
  tendência apanha-o como está.
