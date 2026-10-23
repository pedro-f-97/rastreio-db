# Plano: classificar as subcategorias de despesa

Estado: **executado** (passos 4.1 a 4.5). Falta a verificação com os dados reais
(secção 5), numa cópia da BD.

Pequenas decisões tomadas durante a execução:

- Em `por-categoria`, uma subcategoria extraordinária tem `mes_tipico` 0, para
  as subcategorias somarem o valor da categoria; a página mostra «0,00 €».
- Uma classificação numa categoria que não é de despesa (só possível com a BD
  escrita à mão) é ignorada nas estatísticas.
- As médias da página calculam-se a partir dos meses já arredondados ao
  cêntimo, como as que já existiam.

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
   - **Extraordinária**: compra isolada, que não se espera repetir nos próximos
     dois ou três anos (o carro, o PC).
   - Sem classificação: conta como até agora.
2. As despesas anuais (o seguro, o IUC) **não** são extraordinárias. Contam na
   média, repartidas pelos meses.
3. A classificação é da subcategoria e vale para todas as suas transações. Para
   separar compras grandes das pequenas na mesma subcategoria, cria-se outra
   subcategoria (por exemplo, «PC» à parte de «Hardware»). Não há marca por
   transação.
4. O «mês típico» calcula-se com a **média** das despesas sem as extraordinárias.
5. As extraordinárias **nunca desaparecem**: mostram-se sempre à parte, com o
   total do período. Esconder o seu custo foi o erro que se quis evitar.
6. A classificação «Essencial»/«Evitável» serve para mostrar quanto da despesa
   se podia cortar.

## 3. Decisões tomadas sobre o ecrã (22/10/2026)

As maquetas foram feitas com dados fictícios; escolheu-se a opção B.

1. **Como mostrar nas Estatísticas** (opção B):
   - O cartão «Despesas mensais» dá lugar ao cartão **«Mês típico (sem
     extraordinárias)»**: «Despesa média» (sem as extraordinárias) e
     «Extraordinárias no período» (o total).
   - Por baixo dos cartões, uma barra **«Composição do mês típico»**: Essencial,
     Evitável e Sem classificação, com o valor médio mensal e a percentagem de
     cada um.
   - Uma secção nova **«Despesas extraordinárias»**: a lista das transações
     extraordinárias do período (data, descrição, subcategoria, valor), com uma
     linha de total. Os reembolsos aparecem na lista e reduzem o total.
   - O gráfico da evolução mensal fica como está.
2. **A média e a mediana actuais**: saem dos cartões (decisão 3.1). Na tabela
   «Por categoria» **ficam como estão** e junta-se uma coluna **«Mês típico»**
   (a média sem as extraordinárias). A linha «Despesas» dessa coluna bate certo
   com o cartão «Mês típico».
3. **A poupança e a taxa de poupança**: a versão sem extraordinárias aparece
   **só nos cartões**. O cartão da poupança passa a ter «Média» e «Sem
   extraordinárias»; o da taxa, «Do período» e «Sem extraordinárias». O gráfico
   da taxa de poupança fica como está, com as extraordinárias.
4. **As subcategorias que não são de despesa**: a classificação só aparece e só
   se aceita nas subcategorias de categorias de despesa. Quando uma categoria
   deixa de ser de despesa, as classificações das suas subcategorias **apagam-se**
   (ficam sem classificação); se voltar a ser de despesa, classificam-se de novo.
5. **Os nomes**: «Essencial», «Evitável» e «Extraordinária».

## 4. Passos (modelo → schema → router → api → página)

### 4.1 Modelo e migração (`backend/database.py`)

- Enum novo `ClasseDespesa` (`essencial`, `evitavel`, `extraordinaria`), como os
  outros enums.
- `Subcategoria.classe_despesa`: `SAEnum(ClasseDespesa)`, nullable (NULL quer
  dizer sem classificação).
- Migração nova **no fim** de `MIGRACOES`, `acrescentar_classe_despesa(caminho)`,
  igual a `acrescentar_importacao_id`: um `ALTER TABLE subcategorias ADD COLUMN
  classe_despesa VARCHAR(14)` que pode ser NULL (o tamanho é o do nome mais
  comprido, `extraordinaria`; confirmar o que o `SAEnum` gera). Não reescreve a
  tabela, por isso os IDs e as chaves ficam como estão. Idempotente: não faz nada
  se já houver a coluna ou se faltar a tabela.
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
  aceitá-la ao criar e ao editar uma subcategoria só se a categoria for de
  despesa (decisão 3.4). Ao mudar o tipo de uma categoria para outro que não
  despesa, pôr a NULL a classificação das suas subcategorias.
- `routers/estatisticas.py`:
  - `resumo_mensal`: separar a despesa de cada mês em
    essencial/evitável/extraordinária/sem classificação em `_calculate_totals`.
    As médias continuam a calcular-se na página, a partir dos meses (como hoje).
    Não inventar regras novas para os meses: manter as de «Decisões de design»
    (todos os meses com transações contam, mesmo incompletos).
  - `por_categoria`: a média sem as extraordinárias para a coluna «Mês típico»,
    por categoria e por subcategoria.
  - Um endpoint para a lista das transações extraordinárias do período (com o
    filtro de ano, como os outros).
- Os reembolsos seguem a regra de sempre: um valor positivo numa subcategoria
  extraordinária reduz a despesa extraordinária.

### 4.3 Frontend

- `frontend/src/api/categorias.js`: enviar `classe_despesa` ao criar/editar.
- `frontend/src/api/estatisticas.js`: a chamada da lista das extraordinárias.
- `pages/Categorias.jsx`: um `<select>` na edição da subcategoria, junto à caixa
  do Património, só nas categorias de despesa, e uma etiqueta na lista, como a do
  `trata_patrimonio`. Reutilizar as classes de `componentes.css`.
- `pages/Estatisticas.jsx`: o que se decidiu na secção 3.
- `pages/Sobre.jsx`: explicar a classificação, como se explica o
  `trata_patrimonio`.

### 4.4 Documentação

- `README.md`, «Decisões de design»: as decisões das secções 2 e 3.
- `docs/modelo-dados.md`: o enum novo e o campo da subcategoria.

### 4.5 Testes (`backend/tests/test_api_estatisticas.py`, `test_api_categorias.py`)

Valores calculados à mão, com a conta em comentário, e enums reais. Casos
mínimos:

- criar, editar e tirar a classificação de uma subcategoria;
- recusar a classificação numa subcategoria de uma categoria que não é de
  despesa;
- mudar o tipo de uma categoria de despesa apaga as classificações das suas
  subcategorias;
- uma despesa extraordinária não entra no «mês típico» mas entra no total e na
  lista das extraordinárias;
- um reembolso numa subcategoria extraordinária reduz o total das
  extraordinárias;
- uma subcategoria sem classificação conta como até agora;
- uma subcategoria anual (por exemplo, o seguro) classificada como essencial
  entra na média, repartida pelos meses;
- a coluna «Mês típico» de `por_categoria` e o filtro de ano da lista;
- as transferências continuam de fora.

Verificar os testes novos por mutação numa cópia em `/tmp` (ver `AGENTS.md`).

## 5. Verificação com os dados reais (numa cópia)

Com «Compra Twingo» e «Hardware» classificadas como extraordinárias, e nada
mais, a despesa mensal média sem as extraordinárias deve dar (contas feitas
sobre a BD de 22/10/2026, com os meses que o programa conta hoje):

| Período | Meses | Média actual | Sem extraordinárias | Extraordinárias no período |
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
- Nos cartões das Estatísticas, o «€» passa para a linha de baixo com o ecrã a
  1400 px de largura.
- O gráfico da taxa de poupança desce a valores muito negativos (-315 % nos dados
  das maquetas) nos meses de uma compra grande, e esmaga o resto da linha.
