# Modelo de dados

Modelos SQLAlchemy definidos em `backend/database.py`. Base de dados SQLite, ficheiro único em `dados/rastreio.db`.

## Convenções de sinal

O dinheiro que sai é **negativo** e o que entra é **positivo**, em todo o lado:

- `Transacao.valor`: uma despesa é negativa, uma receita positiva;
- o `custo_total` devolvido por `GET /api/patrimonio/ativos/{id}/resumo` é o
  custo de aquisição com sinal negativo (`-200.00` para uma compra de 200 €), e
  é assim que a página Ativos o mostra. O frontend **soma** o custo ao valor
  actual para obter a mais-valia (`Patrimonio.jsx`: `totalInvestimentos +
  totalCusto`); as percentagens usam `Math.abs(custo)`. Trocar o sinal de um
  dos lados sem o outro dá uma mais-valia errada sem nenhum erro.

`MovimentoAtivo.valor_total` é a excepção: o cálculo usa sempre `abs()`, pelo
que o sinal gravado não altera nada.

## Enums

| Enum | Valores |
|---|---|
| `TipoCategoria` | `despesa`, `receita`, `investimento`, `transferencia` |
| `ClasseDespesa` | `essencial`, `evitavel`, `extraordinaria` |
| `TipoMovimento` | `compra`, `venda`, `dividendo` |
| `TipoContabilizacao` | `investimento`, `patrimonio` |
| `ModoValor` | `coluna_unica`, `duas_colunas` |
| `TipoFicheiro` | `xlsx`, `csv` |

## Configuracao

| Campo | Tipo | Notas |
|---|---|---|
| id | int | PK |
| inicializado | bool | default `False` |
| tour_visto | bool | default `False` |

## Conta

| Campo | Tipo | Notas |
|---|---|---|
| id | int | PK |
| nome | str(100) | obrigatório, único |
| saldo_referencia | float | obrigatório, default `0` |
| data_referencia | date | obrigatório — o `saldo_referencia` é o saldo no fim deste dia: para um dia depois dele somam-se as transacções em ]data_referencia, dia]; para um dia antes, tiram-se as de ]dia, data_referencia]. O saldo de hoje e a evolução usam o mesmo cálculo (`saldo_conta_em`) |
| ativa | bool | default `True` |

**Relações:** 1:N com `Transacao` (`transacoes`), 1:N com `PerfilImportacao` (`perfis_importacao`)

## Categoria

| Campo | Tipo | Notas |
|---|---|---|
| id | int | PK |
| nome | str(100) | obrigatório, único |
| tipo | `TipoCategoria` | obrigatório |

**Relações:** 1:N com `Subcategoria` (`subcategorias`)

## Subcategoria

| Campo | Tipo | Notas |
|---|---|---|
| id | int | PK |
| nome | str(100) | obrigatório |
| trata_patrimonio | bool | default `False` |
| categoria_id | int | FK → `categorias.id`, obrigatório |
| classe_despesa | `ClasseDespesa` | opcional; NULL é sem classificação. Só nas subcategorias de categorias de despesa: a API recusa-a nas outras, e apaga-a quando a categoria deixa de ser de despesa. Acrescentada pela 4.ª migração (`acrescentar_classe_despesa`) |

**Relações:** N:1 com `Categoria` (`categoria`), 1:N com `Transacao` (`transacoes`)

## Transacao

| Campo | Tipo | Notas |
|---|---|---|
| id | int | PK |
| data | date | obrigatório |
| descricao | str(255) | obrigatório |
| valor | float | obrigatório |
| saldo | float | opcional |
| notas | str(500) | opcional |
| categoria_id | int | FK → `categorias.id`, opcional |
| subcategoria_id | int | FK → `subcategorias.id`, opcional |
| conta_id | int | FK → `contas.id`, opcional |
| importacao_id | int | FK → `importacoes.id`, opcional — a importação que trouxe a transação; desfazê-la apaga as transações com o seu id |

**Relações:** N:1 com `Conta`, N:1 com `Categoria`, N:1 com `Subcategoria`

## Importacao

Uma importação que inseriu pelo menos uma transação. Uma importação só com linhas duplicadas não fica registada.

| Campo | Tipo | Notas |
|---|---|---|
| id | int | PK |
| data_hora | datetime | obrigatório — hora local do pedido |
| conta_id | int | FK → `contas.id`, obrigatório |
| ficheiro | str(255) | obrigatório — o nome com que o ficheiro foi enviado |
| inseridas | int | obrigatório |
| duplicadas | int | obrigatório |

**Relações:** N:1 com `Conta` (`conta`)

**Uso:** só a de maior `id` de cada conta se pode desfazer (`DELETE /api/importacao/{id}`); desfeita, o registo é apagado.

## RegraCategorizacao

| Campo | Tipo | Notas |
|---|---|---|
| id | int | PK |
| palavra_chave | str(100) | obrigatório, único |
| categoria_id | int | FK → `categorias.id`, opcional — `null` = "nunca categorizar" |
| subcategoria_id | int | FK → `subcategorias.id`, opcional |

**Relações:** N:1 com `Categoria`, N:1 com `Subcategoria`

## PerfilImportacao

| Campo | Tipo | Notas |
|---|---|---|
| id | int | PK |
| nome | str(100) | obrigatório, único |
| tipo_ficheiro | `TipoFicheiro` | obrigatório, default `xlsx` |
| linha_inicio_dados | int | obrigatório |
| coluna_data | int | obrigatório |
| formato_data | str(50) | obrigatório |
| coluna_descricao | int | obrigatório |
| modo_valor | `ModoValor` | obrigatório |
| coluna_valor | int | opcional — usado se `modo_valor = coluna_unica` |
| coluna_debito | int | opcional — usado se `modo_valor = duas_colunas` |
| coluna_credito | int | opcional — usado se `modo_valor = duas_colunas` |
| separador_decimal | str(1) | obrigatório, default `"."` |
| tem_saldo | bool | obrigatório, default `False` |
| coluna_saldo | int | opcional |
| coluna_fee | int | opcional |
| conta_id | int | FK → `contas.id`; obrigatório ao criar e ao editar o perfil, e a importação recusa um perfil que o tenha perdido (a coluna aceita `NULL`, por perfis antigos) |

**Relações:** N:1 com `Conta` (`conta`)

## TipoAtivo

Tabela (não é enum), editável na página Tipos de Ativo. Os valores iniciais vêm de `SEED_TIPOS_ATIVO` (`dados_iniciais.py`), semeados por `POST /api/configuracao/inicializar`.

| Campo | Tipo | Notas |
|---|---|---|
| id | int | PK |
| nome | str(100) | obrigatório, único |
| tem_unidades | bool | default `False` — `True`: o custo segue FIFO por unidades e o valor é quantidade × último preço ou, sem preço, o custo; `False`: custo acumulado, e o valor actual vem do último preço registado ou, sem preço, é o custo |

**Relações:** 1:N com `Ativo` (`ativos`)

## Ativo

| Campo | Tipo | Notas |
|---|---|---|
| id | int | PK |
| nome | str(100) | obrigatório |
| tipo_id | int | FK → `tipos_ativo.id`, obrigatório |
| simbolo | str(20) | opcional, único |
| moeda | str(10) | default `"EUR"` |
| notas | str(500) | opcional |
| contabilizacao | `TipoContabilizacao` | obrigatório — determina onde o valor do ativo conta no património: em investimentos (`investimento`) ou em bens (`patrimonio`). O ramo de cálculo (FIFO ou custo acumulado) é decidido por `TipoAtivo.tem_unidades` |

**Relações:** N:1 com `TipoAtivo` (`tipo`), 1:N com `MovimentoAtivo` (`movimentos`), 1:N com `PrecoAtivo` (`precos`)

## MovimentoAtivo

| Campo | Tipo | Notas |
|---|---|---|
| id | int | PK |
| ativo_id | int | FK → `ativos.id`, obrigatório |
| transacao_id | int | FK → `transacoes.id`, opcional |
| tipo_movimento | `TipoMovimento` | obrigatório |
| data | date | obrigatório |
| quantidade | float | opcional |
| preco_unitario | float | opcional |
| comissao | float | opcional, default `0` |
| valor_total | float | obrigatório |
| notas | str(500) | opcional |

**Relações:** N:1 com `Ativo` (`ativo`), N:1 com `Transacao` (`transacao`)

## PrecoAtivo

| Campo | Tipo | Notas |
|---|---|---|
| id | int | PK |
| ativo_id | int | FK → `ativos.id`, obrigatório |
| data | date | obrigatório |
| preco | float | obrigatório |

**Relações:** N:1 com `Ativo` (`ativo`)

**Restrições:** `UNIQUE(ativo_id, data)` — um preço por activo e por dia

**Uso:** o valor actual de um activo (resumo e ponto de hoje da evolução) usa o preço mais recente, mesmo com data futura, e a página Ativos assinala-o com «⚠» (a API recusa preços novos com data futura, e os preços podem ser listados e apagados); os pontos passados da evolução usam o último preço até essa data.