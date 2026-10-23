# Plano: as médias e as taxas das Estatísticas sem o mês em curso

Estado: **executado** (passos 4.1 a 4.4), no mesmo ramo do crescimento do
património (`feat/crescimento-patrimonio`). Falta a verificação com os dados
reais (secção 5), numa cópia da BD.

Pequenas decisões tomadas durante a execução:

- Uma categoria que só tem transações no mês em curso não aparece na tabela
  «Por categoria» (não tem nenhum mês completo); com só o mês em curso no
  período, a tabela fica vazia.
- As «Extraordinárias no período» são uma soma: contam o mês em curso.

## 1. O problema

O mês em curso está incompleto, mas conta como um mês inteiro nas médias, nas
medianas e nas taxas das Estatísticas. Se o salário já entrou e as despesas do
mês ainda não, a poupança média e a taxa de poupança sobem; a despesa média
desce. A decisão de design em vigor diz o contrário («as médias mensais das
estatísticas contam todos os meses que têm transações»), por isso muda-se e
regista-se a mudança.

## 2. Decisões já tomadas (23/10/2026)

1. **Regra A (calendário):** o mês em curso é o mês de hoje. Um mês passado com
   o extracto incompleto continua a contar (fica no ponto 6, fora do âmbito).
2. **Saem do mês em curso**, na página Estatísticas:
   1. o cartão do mês típico («Despesa média») e a «Composição do mês típico»;
   2. o cartão «Poupança mensal» (média e sem extraordinárias);
   3. o cartão «Taxa de poupança» (do período e sem extraordinárias);
   4. as médias de 3 e de 12 meses do gráfico da taxa de poupança: o mês em
      curso fica sem valor nas duas linhas;
   5. a tabela «Por categoria»: a média, a mediana e o mês típico, nas linhas
      de grupo e nas categorias e subcategorias.
3. **Ficam como estão:** os totais e as somas (as extraordinárias no período,
   a distribuição por categoria, o Histórico, o detalhe de um mês), as barras
   do gráfico mensal e o gráfico da taxa de poupança mês a mês. O dinheiro
   desses dias existe, e tirá-lo esconderia transações.
4. **Um ano passado não muda:** o mês em curso só existe no filtro «Todos» e no
   ano corrente.

## 3. Pequenas decisões

5. **«Hoje» vem do backend**, para haver uma só fonte e poder testá-la:
   `resumo-mensal` marca cada mês com `em_curso` (verdadeiro só no mês de hoje),
   e `por-categoria` deixa esse mês de fora das contas.
6. **Sem nenhum mês completo** (por exemplo, o filtro do ano corrente em
   janeiro), as médias e as taxas mostram «—» em vez de 0.
7. Os cartões e a tabela não dizem nada sobre o mês em curso: a regra fica
   explicada nos Conceitos e no README.

## 4. Passos

### 4.1 Backend (`backend/routers/estatisticas.py`)

- `resumo_mensal`: cada mês leva `em_curso: bool`, comparando com
  `date.today()`.
- `por_categoria`: tirar o mês de hoje de `meses_distintos` e das linhas
  agregadas, antes de calcular a média, a mediana e o mês típico. Com `ano` de
  um ano passado, nada muda.
- `por-subcategoria`, `extraordinarias` e `detalhe-mensal` não mudam (são
  totais).

### 4.2 Frontend (`frontend/src/pages/Estatisticas.jsx`)

- Os cartões (pontos 2.1 a 2.3) e as linhas de grupo da tabela (2.5) calculam-se
  a partir dos meses filtrados sem os `em_curso`.
- `taxaMovel`: `null` no mês `em_curso` (2.4); as janelas dos outros meses não
  mudam.
- Ponto 6: «—» quando não há meses completos.

### 4.3 Documentação

- README, «Decisões de design»: trocar a frase das médias mensais pela regra
  nova.
- Página Conceitos: uma frase na secção das Estatísticas (ou na do mês típico).

### 4.4 Testes (`backend/tests/test_api_estatisticas.py`)

Valores escritos à mão, com `date.today()` do router fixo:

- `resumo-mensal`: `em_curso` verdadeiro só no mês de hoje; os testes que
  comparam o dicionário inteiro ganham o campo, a `False`.
- `por-categoria`, com «Todos» e com o ano corrente: a média, a mediana e o mês
  típico sem o mês de hoje (por exemplo, 100 e 200 em meses completos e 10 no
  mês em curso dão média 150, e não 103,33).
- `por-categoria` de um ano passado: igual ao de hoje.
- Só o mês em curso no período: a tabela vem vazia (a página mostra «—» nos
  cartões).

O frontend não tem testes: verifica-se com `npm run lint` e à mão, numa BD de
teste. Verificar os testes novos por mutação numa cópia em `/tmp`.

## 5. Verificação com os dados reais (numa cópia)

Fica do lado do utilizador: com a cópia da BD de hoje (23/10/2026), os cartões
de «Todos» e de 2026 deixam de contar outubro.

## 6. Fora do âmbito (ficam registados, não se tratam aqui)

- **Regra B:** um mês passado com o extracto incompleto (setembro de 2026 só tem
  até dia 7) continua a contar como inteiro, aqui e no crescimento do
  património. Resolvê-lo exige saber até que dia chega cada extracto, que hoje
  não se guarda.
- A taxa anual do Histórico, no ano corrente, é a de um ano parcial.
