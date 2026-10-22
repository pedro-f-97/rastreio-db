# Plano: classificar as subcategorias de despesa

Estado: **por executar**. Antes de escrever código, responder às decisões em
aberto (secção 3), **uma de cada vez**, e só depois seguir os passos.

## 1. O problema

Nas Estatísticas, a média e a mediana mensais enganam, cada uma à sua maneira
(números da BD real em 22/10/2026):

- **A média é puxada pelas compras isoladas.** A despesa mensal média em «Todos»
  é 921,76 €, por causa do Twingo (11 990 €) e do Hardware (2 661,87 €).
- **A mediana esquece as despesas que não são de todos os meses.** O seguro
  (361 € a 401 €), o IUC e a inspeção pagam-se uma vez por ano. Para a mediana,
  é como se não existissem.
- As alternativas habituais (a média aparada, a média sem os meses extremos)
  tiram meses inteiros e, com eles, a despesa normal desses meses. No
  investimento continuam a dar valores sem sentido.

O problema de fundo é que tudo é somado por mês antes de se fazerem as contas.
A solução é tirar da média as **transações** fora do comum, e não os meses.

## 2. Decisões já tomadas

1. Cada subcategoria de despesa tem **uma** classificação, escolhida entre três
   (uma escolha única, e não três caixas sim/não):
   - **Essencial**: precisa-se e repete-se (Combustível, Supermercado, Renda,
     Seguro, IUC, Inspeção).
   - **Evitável**: dispensável e repete-se (Restauração, Jogos, Viagens).
   - **Esporádica**: compra isolada, que não se espera repetir nos próximos dois
     ou três anos (o carro, o PC).
   - Sem classificação: conta como até agora.
2. As despesas anuais (o seguro, o IUC) **não** são esporádicas. Contam na média,
   repartidas pelos meses.
3. A classificação é da subcategoria e vale para todas as suas transações. Para
   separar compras grandes das pequenas na mesma subcategoria, cria-se outra
   subcategoria (por exemplo, «PC» à parte de «Hardware»). Não há marca por
   transação.
4. O «mês típico» calcula-se com a **média** das despesas sem as esporádicas.
5. As esporádicas **nunca desaparecem**: mostram-se sempre à parte, com o total
   do período. Esconder o seu custo foi o erro que se quis evitar.
6. A classificação «Essencial»/«Evitável» serve para mostrar quanto da despesa
   se podia cortar.

## 3. Decisões em aberto (perguntar uma de cada vez)

1. **Como mostrar nas Estatísticas.** Por exemplo: um cartão novo «Mês típico»
   (a média sem as esporádicas), ao lado do total das esporádicas no período; a
   divisão Essencial/Evitável como cartão ou como gráfico. Desenhar as opções e
   mostrá-las antes de as implementar.
2. **O que fazer à mediana e à média actuais** nos cartões e na tabela «Por
   categoria»: ficam como estão, são substituídas, ou ficam só nalguns sítios.
3. **A poupança e a taxa de poupança** também passam a ter versão sem
   esporádicas? (Sem o carro, a poupança média de «Todos» passa de 158 € para
   572 €.)
4. **As subcategorias que não são de despesa** (receita, investimento,
   transferência): sugestão, a classificação só aparece e só se aceita nas
   subcategorias de categorias de despesa. Confirmar o que acontece quando uma
   categoria muda de tipo e as suas subcategorias já estão classificadas.
5. **Os nomes**: «Essencial», «Evitável», «Esporádica», ou outros.

## 4. Passos (modelo → schema → router → api → página)

### 4.1 Modelo e migração (`backend/database.py`)

- Enum novo `ClasseDespesa` (`essencial`, `evitavel`, `esporadica`), como os
  outros enums.
- `Subcategoria.classe_despesa`: `SAEnum(ClasseDespesa)`, nullable (NULL quer
  dizer sem classificação).
- Migração nova **no fim** de `MIGRACOES`, `acrescentar_classe_despesa(caminho)`,
  igual a `acrescentar_importacao_id`: um `ALTER TABLE subcategorias ADD COLUMN
  classe_despesa VARCHAR(10)` que pode ser NULL. Não reescreve a tabela, por isso
  os IDs e as chaves ficam como estão. Idempotente: não faz nada se já houver a
  coluna ou se faltar a tabela.
- Teste `backend/tests/test_acrescentar_classe_despesa.py`, ao estilo de
  `test_acrescentar_importacao_id.py`: uma BD antiga com o DDL escrito à mão, a
  coluna acrescentada a NULL, os IDs mantidos, a segunda chamada não muda nada
  (MD5 igual), e uma BD nova criada pelo modelo bate certo com uma migrada.
- Correr a migração numa **cópia** da BD real (`RASTREIO_DB_DIR`) antes de tudo.

### 4.2 Schema e router

- `schemas.SubcategoriaCreate`: `classe_despesa: Optional[ClasseDespesa] = None`.
  É preciso poder **tirar** a classificação: usar `model_fields_set`, como o
  `simbolo` em `editar_ativo`, para distinguir «não enviado» de «enviado a
  null».
- `routers/categorias.py`: devolver `classe_despesa` em `listar_categorias`, e
  aceitá-la ao criar e ao editar uma subcategoria (de acordo com a decisão 3.4).
- `routers/estatisticas.py`: devolver o necessário para o que se decidir em 3.1
  a 3.3. A ideia base é separar a despesa de cada mês em
  essencial/evitável/esporádica/sem classificação em `_calculate_totals`, e as
  médias continuam a calcular-se na página, a partir dos meses (como hoje). Não
  inventar regras novas para os meses: manter as de «Decisões de design» (todos
  os meses com transações contam, mesmo incompletos).
- Os reembolsos seguem a regra de sempre: um valor positivo numa subcategoria
  esporádica reduz a despesa esporádica.

### 4.3 Frontend

- `frontend/src/api/categorias.js`: enviar `classe_despesa` ao criar/editar.
- `pages/Categorias.jsx`: um `<select>` na edição da subcategoria, junto à caixa
  do Património, e uma etiqueta na lista, como a do `trata_patrimonio`. Reutilizar
  as classes de `componentes.css`.
- `pages/Estatisticas.jsx`: o que se decidir em 3.1 a 3.3.
- `pages/Sobre.jsx`: explicar a classificação, como se explica o
  `trata_patrimonio`.

### 4.4 Documentação

- `README.md`, «Decisões de design»: as decisões da secção 2 e as respostas da
  secção 3.
- `docs/modelo-dados.md`: o enum novo e o campo da subcategoria.

### 4.5 Testes (`backend/tests/test_api_estatisticas.py`, `test_api_categorias.py`)

Valores calculados à mão, com a conta em comentário, e enums reais. Casos
mínimos:

- criar, editar e tirar a classificação de uma subcategoria;
- uma despesa esporádica não entra no «mês típico» mas entra no total das
  esporádicas;
- um reembolso numa subcategoria esporádica reduz o total das esporádicas;
- uma subcategoria sem classificação conta como até agora;
- uma subcategoria anual (por exemplo, o seguro) classificada como essencial
  entra na média, repartida pelos meses;
- as transferências continuam de fora.

Verificar os testes novos por mutação numa cópia em `/tmp` (ver `AGENTS.md`).

## 5. Verificação com os dados reais (numa cópia)

Com «Compra Twingo» e «Hardware» classificadas como esporádicas, e nada mais, a
despesa mensal média sem as esporádicas deve dar (contas feitas sobre a BD de
22/10/2026, com os meses que o programa conta hoje):

| Período | Meses | Média actual | Sem esporádicas | Esporádicas no período |
|---|---|---|---|---|
| Todos | 29 | 921,76 € | 416,52 € | 14 651,87 € |
| 2025 | 12 | 639,09 € | 460,66 € | 2 141,19 € |
| 2026 | 9 | 481,09 € | 467,02 € | 126,69 € |

O ecrã deve mostrar estes valores. Se mostrar outros, há um erro.

## 6. Fora do âmbito (ficam registados, não se tratam aqui)

- O carro conta como despesa nas Estatísticas, mas no Património é um bem; o
  custo real é a desvalorização (1 490 € até hoje).
- O mês em curso e os meses com importação incompleta contam como meses inteiros
  (setembro de 2026 só tem até dia 7).
- O cartão «Resultados» do Património só mostra percentagens por ativo.
- O património não mostra quanto cresce por mês.
- O saldo do ActivoBank está 10,10 € acima do do banco: falta a saída de 10 € de
  11/06/2025 (a entrada na TradeRepublic existe) e há 0,10 € de diferença em
  13/05/2025.
- O USDC está com o preço de 1,28 € por unidade.
