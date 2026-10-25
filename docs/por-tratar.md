# Por tratar

Os pontos que ficaram de fora dos planos já executados (a classificação das
despesas, o crescimento do património, as médias sem o mês em curso e a
verificação do saldo). Nenhum está decidido: cada um precisa de uma decisão
antes de se implementar.

## Estatísticas

- **O carro conta como despesa**, mas no Património é um bem. O custo real é a
  desvalorização (1 490 € até 22/10/2026). Classificar a compra como
  extraordinária tira-a do mês típico, mas não da média, da poupança nem da taxa
  com tudo.
- **Um mês passado com o extracto incompleto conta como inteiro** (setembro de
  2026 só tem até dia 7), aqui e no crescimento do património. Resolvê-lo exige
  saber até que dia chega cada extracto, que hoje não se guarda.
- **A taxa anual do Histórico, no ano corrente, é a de um ano parcial.**
- **O gráfico da taxa de poupança** desce a valores muito negativos (−315 % nos
  dados das maquetas) nos meses de uma compra grande, e esmaga o resto da linha.
- **Nos cartões, o «€» passa para a linha de baixo** com o ecrã a 1400 px de
  largura.

## Património

- **O cartão «Resultados» só mostra percentagens por ativo**, sem o valor em
  euros (o cartão «Investimentos» já mostra os dois).
- **Uma compra de investimento ainda por tratar (pendente)** tira dinheiro da
  liquidez sem ativo do outro lado, e conta como «menos poupança» no
  crescimento até ser tratada.
- **Um dividendo que entra só como transação**, sem movimento no ativo, conta
  como poupança e não como valorização.
- **Uma conta sem extracto importado em parte do período** fica com o saldo
  parado, e a tendência apanha-o como está.

## Verificação do saldo e importação

- **A ordem das transações dentro do dia não se guarda.** Guardá-la permitiria
  comparar transação a transação, em vez de ao fim do dia, e acabava com os dias
  de «ordem incerta».
- **A importação não avisa quando uma linha coincide com uma transação manual**
  (com a mesma data e valor, mas outra descrição): fica duas vezes, e a manual
  apaga-se à mão.

## Nos dados (não é código)

- **O preço do USDC está a 1,28 €** (registado a 07/09/2026). Distorce o valor
  dos investimentos e a valorização do crescimento (cerca de 30 €/mês em 2026).
- **ActivoBank:** a correção de −10,10 € a 11/06/2025 junta dois erros. Para o
  aviso desaparecer, apaga-se e criam-se duas: −0,10 € a 13/05/2025 (o crédito
  do AliExpress está a +6,15 €, mas o saldo do banco só subiu 6,05 €) e
  −10,00 € a 11/06/2025.
