# Modelo de dados

Modelos SQLAlchemy definidos em `backend/database.py`. Base de dados SQLite, ficheiro único em `dados/rastreio.db`.

## Enums

| Enum | Valores |
|---|---|
| `TipoCategoria` | `despesa`, `receita`, `investimento`, `transferencia` |
| `TipoAtivo` | `etf`, `crypto`, `veiculo`, `imovel`, `outro` |
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
| data_referencia | date | obrigatório |
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

**Relações:** N:1 com `Categoria` (`categoria`), 1:N com `Transacao` (`transacoes`)

## Transacao

| Campo | Tipo | Notas |
|---|---|---|
| id | int | PK |
| data | date | obrigatório |
| descricao | str(255) | obrigatório |
| valor | float | obrigatório |
| saldo | float | opcional |
| reembolso | bool | default `False` |
| notas | str(500) | opcional |
| categoria_id | int | FK → `categorias.id`, opcional |
| subcategoria_id | int | FK → `subcategorias.id`, opcional |
| conta_id | int | FK → `contas.id`, opcional |

**Relações:** N:1 com `Conta`, N:1 com `Categoria`, N:1 com `Subcategoria`

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
| conta_id | int | FK → `contas.id`, opcional |

**Relações:** N:1 com `Conta` (`conta`)

## Ativo

| Campo | Tipo | Notas |
|---|---|---|
| id | int | PK |
| nome | str(100) | obrigatório |
| tipo | `TipoAtivo` | obrigatório |
| simbolo | str(20) | opcional, único |
| moeda | str(10) | default `"EUR"` |
| notas | str(500) | opcional |
| contabilizacao | `TipoContabilizacao` | obrigatório — determina se entra no cálculo FIFO (`investimento`) ou é tratado como património puro (`patrimonio`) |

**Relações:** 1:N com `MovimentoAtivo` (`movimentos`), 1:N com `PrecoAtivo` (`precos`)

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