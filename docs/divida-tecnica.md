# Dívida Técnica

Achados da análise ao código, feita antes de introduzir testes. Nada disto
foi corrigido, excepto os itens marcados como **Resolvido**. O objectivo é
registar o que se sabe, para que a decisão de
mexer em cada ponto seja deliberada e não acidental.

Cada item está numerado (`D1`, `D2`, …) e os testes de caracterização
referenciam o número correspondente em comentários, para que `grep -n "D1"`
mostre onde o comportamento está fixado e onde está documentado. `D1a` é um
sub-item de `D1`.

**Estado da aplicação:** em produção, com dados reais. As correcções que
alterem números já apresentados ao utilizador (D5) exigem backup da BD e
validação manual. As restantes não tocam em dados.

Legenda: 🔴 mexe em dados, ou é perda/erro silencioso · 🟡 resultado incorrecto
mas visível · ⚪ robustez/qualidade

Os itens `D12a`…`D12k` são pontos independentes dentro do mesmo ficheiro,
separados para que o `grep` por `D12e` aponte para um só sítio.

---

## 🔴 D1 — Chaves estrangeiras não são forçadas pelo SQLite

`backend/database.py:88` cria a engine sem `PRAGMA foreign_keys=ON`, e não há
`ON DELETE` nem cascade nas `ForeignKey` declaradas
(`database.py:167, 184-187, 199-200, 236, 244, 259-260, 277`). O SQLite não
aplica chaves estrangeiras por omissão, e as `relationship()` também não
declaram `cascade` (`database.py:158, 251-252`).

Na prática, apagar uma categoria **pode** deixar as transações a apontar para
linhas que já não existem, sem erro. Essas transações desapareceriam das
estatísticas (os joins são `INNER`), apareceriam sem nome na listagem, e não
seriam contadas em `/transacoes/por-categorizar/total`.

### 🔴 D1a — O schema da BD actual aponta para uma tabela que não existe

Isto não é hipotético, é o estado actual, e só apareceu com
`PRAGMA foreign_key_check` (consulta que compara as *definições* das chaves, ao
contrário de um `JOIN`, que não encontra a tabela e por isso reporta zero).

`precos_ativo` e `movimentos_ativo` têm `FOREIGN KEY(ativo_id) REFERENCES
"ativos_old" (id)`, e **`ativos_old` não existe**. A tabela `ativos` existe e
está preenchida (5 linhas, 19 preços, 41 movimentos), mas nenhuma referência
deixa de apontar para ela.

Causa: `old/migrar_tipos_ativo.py:63` faz `ALTER TABLE ativos RENAME TO
ativos_old` e a linha 93 faz `DROP TABLE ativos_old`. Em SQLite >= 3.25 o
`RENAME` reescreve as referências nas outras tabelas para o novo nome, e o
`DROP` apaga a tabela sem as reescrever de volta. O script também não desliga
as FKs — ao contrário de `migrar_regras_categoria_opcional.py:6`, que já faz
`PRAGMA foreign_keys = OFF` antes do `DROP` da linha 22 e por isso escapou.

**Consequência verificada:** com a pragma ligada, um `INSERT` em `precos_ativo`
falha com `no such table: main.ativos_old`, e um `DELETE FROM ativos WHERE
id=1` **passa sem erro** e deixa 2 movimentos órfãos. Como as chaves apontam
para o vazio, não há nada que as faça falhar.

A correcção é recriar as duas tabelas com a referência certa, preservando os
IDs, e só depois avaliar a pragma. Isto é trabalho de script, não de pragma.

**Versões do SQLite relevantes.** A regra de reescrever as referências das
chaves estrangeiras num `RENAME` depende da versão, e por isso o mesmo script
pode deixar o schema partido numa máquina e intacto noutra. Registado aqui para
que a migração seja repetível:

| Onde | Versão |
| --- | --- |
| Python 3.14.6 do `backend/venv` (`import sqlite3`) | 3.51.2 |
| CLI do sistema (`sqlite3 --version`) | 3.51.2 |
| `sys._sqlite3` empacotado pelo PyInstaller | **por confirmar em cada build** |

Coincidem hoje, o que torna a falha mais difícil de reproduzir noutro
ambiente. O executável distributions não usa a CLI nem o `venv`, mas a
biblioteca que o Python inclui — e essa muda com a versão do Python que gerou o
build. Antes de correr a migração em produção, confirmar a versão embutida e
testar o script contra ela, não contra o `venv`.

### O resto do risco de activar a pragma

**Verificado na BD actual:** zero órfãos em `transacoes.categoria_id`,
`transacoes.subcategoria_id`, `transacoes.conta_id` e
`subcategorias.categoria_id` (que também não tem NULLs), e
`PRAGMA integrity_check` devolve `ok`. `PRAGMA foreign_key_check` só reporta as
violações de D1a. **Não é preciso script de limpeza de órfãos**, e
`criar_tabelas()` não falha — emitir DDL não varre dados, e a pragma só é
avaliada no momento de escrever.

Quanto aos endpoints, a hipótese (a confirmar com testes de caracterização) é
que os `DELETE` sobre tabelas-pai passem a falhar por violação de FK onde antes
devolviam 200. Lidos os quatro handlers:

- `apagar_categoria` (`routers/categorias.py:59`) — `db.delete(cat)` sem
  qualquer pré-checagem. **Passa a falhar.**
- `apagar_subcategoria` (`routers/categorias.py:91`) — idem, sem pré-checagem.
  **Passa a falhar.**
- `apagar_ou_desativar_conta` (`routers/contas.py:40-52`) — **já faz
  pré-checagem**: se houver transações, desactiva a conta em vez de a apagar
  (linha 49). Não é afectado.
- `apagar_tipo_ativo` (`routers/tipos_ativo.py:35-41`) — **já faz
  pré-checagem** (`if tipo.ativos` na linha 39 devolve 409). Mas
  `ativos.tipo_id` é `NOT NULL`, e a pré-checagem só protege se a lista
  `tipo.ativos` estiver carregada e em dia.

Comprovado em cópia temporária da BD, com a pragma ligada: `DELETE` em
`categorias` falha para as categorias 5, 6 e 11, e `DELETE` em `tipos_ativo`
falha para os tipos 1, 3 e 7, com `IntegrityError` no SQLAlchemy. Ou seja,
**três dos quatro endpoints ficam com erro** se a pragma for activada sem mais
nada.

Nota de método: a CLI do `sqlite3` e o SQLAlchemy concordam quando testam a
mesma tabela (verificado em `tipos_ativo` id=1: ambas falham). Uma leitura
preliminar sugeria divergência, mas vinha de comparar tabelas diferentes
(`tipos_ativo` por um lado, `ativos` por outro) — `ativos` é justamente a tabela
cuja FK não é verificada, por causa de D1a. Não há divergência entre as duas
vias, e a versão do SQLite não entra na questão.

Para activar: `PRAGMA foreign_keys=ON` por conexão, via
`event.listens_for(engine, "connect")` em `database.py` (é por conexão, e o
pool recicla). Antes disso é preciso corrigir D1a e decidir a política de
`ON DELETE`, porque `ON DELETE CASCADE` muda o comportamento dos endpoints.

## 🟡 D2 — `total` do património não bate com a soma dos componentes

`backend/servicos/patrimonio_serv.py:152-158` soma os três blocos em ponto
flutuante e só depois arredonda:

```python
total = liquidez + investimentos + ativos_fisicos   # linha 152
return {..., "liquidez": round(liquidez, 2), ..., "total": round(total, 2)}
```

O arredondamento é aplicado aos quatro separadamente, a partir da mesma soma
não arredondada. Os três componentes podem somar 1 cêntimo diferente do `total`
apresentado.

**Impacto na UI:** só quando os arredondamentos caem em lados opostos do
cêntimo. É uma diferença de apresentação, não de dados: a BD não muda, e os
valores por ativo estão correctos. Mas é visível **dentro do mesmo ecrã** —
`frontend/src/pages/Patrimonio.jsx:212-215` desenha a série `Total` ao lado de
`Liquidez`, `Investimentos` e `Bens` no mesmo gráfico, com os quatro valores
visíveis lado a lado.

Correção: arredondar cada componente e somar os arredondados, ou somar em
`Decimal`.

## 🟡 D3 — Boundary de data de referência diverge entre dois endpoints

A mesma conta é calculada de duas maneiras incompatíveis:

- `backend/servicos/patrimonio_serv.py:112` — `Transacao.data > conta.data_referencia`
- `backend/routers/contas.py:62` — `data >= :data_referencia`

Uma transação exactamente na data de referência entra no saldo de
`/api/contas/{id}/saldo` e não entra no `/api/patrimonio/evolucao`. O
utilizador vê dois saldos diferentes para a mesma conta.

É uma decisão de negócio, não um erro evidente: "saldo de referência" pode
significar "antes desta data" ou "até esta data, exclusive". Tem de ser
escolhido um dos dois e propagado.

## 🟡 D4 — Receita negativa desaparece de todos os totais

`backend/routers/estatisticas.py:268-289` (`_calculate_totals`):

```python
if t.categoria.tipo == receita and not t.reembolso and t.valor > 0:  # 280
elif t.categoria.tipo == investimento:                              # 282
elif t.valor < 0 and t.categoria.tipo != receita:                   # 284
elif t.valor > 0 and t.reembolso:                                   # 286
```

Os números são das linhas da condição; a soma correspondente está logo a seguir,
nas linhas 281, 283, 285 e 287.

Uma transação de categoria `receita` com `valor` negativo (estorno, devolução
de receita recebida) não satisfaz a linha 280 (`valor > 0` falha), nem a 284
(exclui explicitamente receitas). Não cai em nenhuma branch: **desaparece sem
ser somada a nada**, e o mês fecha sem esse valor.

## 🟡 D5 — Transferências contaminam o denominador das médias

`backend/routers/estatisticas.py:59-65` conta os meses distintos numa query
que **não** exclui transferências; a query de totais (`linha 68+`) exclui
(`Categoria.tipo != transferencia`, linha 77).

Consequência: meses em que houve apenas transferências entram no denominador
sem entrarem no numerador, pelo que **todas as médias mensais de
`/por-categoria` e `/por-subcategoria` são sistematicamente baixas**. A
mediana não é afetada (usa a lista sem preenchimento, linha 110).

Agravado pelo facto de `/por-categoria` e `/por-subcategoria` usarem
estratégias de preenchimento diferentes: `media` preenche com zeros
(linhas 109, 115), `mediana` não (linhas 110, 116). As duas medidas estão a
ser calculadas sobre populações diferentes, o que as torna não comparáveis
entre si.

## 🔴 D6 — Restauro de backup valida só 3 das 11 tabelas

`backend/routers/backups.py:13`:

```python
TABELAS_ESPERADAS = {"transacoes", "categorias", "contas"}
```

Um ficheiro `.db` que não tenha `ativos`, `movimentos_ativo`, `precos_ativo`,
`regras_categorizacao`, `perfis_importacao`, `tipos_ativo`, `subcategorias` ou
`configuracao` **passa a validação** (linha 91) e é restaurado. A verificação
pós-restauração (linha 112) volta a contar as mesmas 3 tabelas e dá tudo certo.

A validação prévia (linhas 62-105) só verifica os nomes das tabelas. A
verificação posterior (linhas 112-127) repete esse mesmo teste sobre as 3
tabelas esperadas. **Não verifica colunas**: um `.db` com as 3 tabelas
esperadas mas que tenha apenas a coluna `id` nessas tabelas é aceite com `200
OK` e a base de dados fica inutilizável (quando se tenta ler tabelas existentes
no modelo, SQLAlchemy levanta `OperationalError: no such column ...`).

Resultado: um backup antigo ou de outra instalação é aceite, o `.anterior` de
segurança é apagado (linhas 129-131) e o património inteiro — movimentos e
preços — desaparece sem qualquer aviso. Como o `.anterior` só se apaga *depois*
de tudo confirmar, e a confirmação é fraca, não há forma de recuperar.

A lista das tabelas esperadas está fixada por testes de caracterização
(`backend/tests/test_backups/`) com os nomes reais do modelo. Esses testes não
garantem a derivação automática da lista: quando `TABELAS_ESPERADAS` passar a
derivar de `Base.metadata.sorted_tables` (fonte de verdade), os testes de
caracterização irão falhar de propósito, para serem invertidos.

O que ficou por cobrir: o único caminho que usa o ficheiro `.anterior` (rollback
no bloco `except Exception`) não é atingível com os ficheiros construídos nos
testes — o docstring mantém «Rollback por cobrir» por esse motivo. Não há caso
de teste que consiga atingir esse ramo com uma base de dados temporária válida
antes da substituição.

**O que os testes mediram:** para um `.db` que contém apenas as 3 tabelas
esperadas (sem as restantes 8), o endpoint devolve `200 {"ok": true, "mensagem":
"Base de dados restaurada"}` e, ao ler uma tabela que não existe no novo estado
(exemplo: `ativos`), o acesso levanta `OperationalError: no such table: ativos`.
Este é o mesmo defeito que estava anotado como `xfail` no commit 398130b.

## 🟡 D7 — Precedência das regras de categorização é não determinística

`backend/importador_transacoes.py:26` faz `db.query(RegraCategorizacao).all()`
sem `ORDER BY`. A ordem das linhas devolvidas depende do plano de execução do
SQLite e pode mudar após um `VACUUM`, uma migração, ou uma mudança de versão.
Duas importações do mesmo ficheiro podem categorizar transações de formas
diferentes, sem que nada tenha mudado.

### O `break` da fase 2 (linha 23)

Para a primeira regra cuja `palavra_chave` casa, `aplicar_regras` executa o
`break` **incondicionalmente** — a instrução está dentro do `if` de
correspondência (linha 17), não dentro de nenhum dos ramos de atribuição. E
"casou" não é o mesmo que "atribuiu". As linhas 18-21 só atribuem em dois
casos:

- `transacao.categoria_id is None` (linha 18) — atribui categoria e
  subcategoria;
- a transação já tem **a mesma** categoria e `subcategoria_id is None`
  (linha 21) — atribui só a subcategoria.

Nos restantes casos — a transação já tem uma categoria **diferente** da que a
regra define, ou já tem a mesma categoria mas com subcategoria — **não é
atribuído nada, e mesmo assim a regra é consumida**: o `break` interrompe o
ciclo e nenhuma regra posterior é avaliada. Uma transação que já estava
categorizada fica sem a subcategoria que a segunda regra lhe traria, sem erro
nem registo.

Os dois lados do `break` estão fixados por dois testes em
`backend/tests/test_importador_regras.py`:
`test_break_impede_a_segunda_regra_de_atribuir_a_subcategoria`, em que a 1.ª
regra atribui a categoria e deixa a subcategoria a `None` e a 2.ª seria a que a
preenchia, e `test_regra_consumida_sem_atribuir_deixa_a_transacao_sem_subcategoria`,
em que a 1.ª regra casa com outra categoria e consome o ciclo sem atribuir nada.
É este último que observa o caso "consumida sem atribuir" numa transação que o
utilizador já tinha em `(5, None)`: a 1.ª regra casa com a categoria 2, `5 == 2`
é falso, e a 2.ª regra — que traria a subcategoria 50 — nunca é avaliada. Nos
dois testes a ausência do `break` mudaria o resultado: `(1, 20)` em vez de
`(1, None)`, e `(5, 50)` em vez de `(5, None)`.

## 🟡 D8 — Motor de regras duplicado com semântica divergente

A mesma lógica de duas fases existe em três sítios:

| Sítio | Correspondência |
|---|---|
| `importador_transacoes.py:5` (`aplicar_regras`) | `palavra_chave.upper() in descricao.upper()` |
| `routers/regras.py:94` (`pre_visualizar_regras`) | igual, mas pré-filtra `subcategoria_id IS NULL` (linha 88) |
| `routers/regras.py:54` (`criar_regra`, backfill) | SQL `ilike` — **ASCII-only** |

Consequências: (a) o preview e a aplicação não veem o mesmo conjunto, logo as
contagens não batem; (b) `ilike` não casa acentos, `upper()` casa — uma regra
com "ç" funciona na importação e não no backfill; (c) `palavra_chave` com `%`
ou `_` é injectado como wildcard no `ilike` (linha 54) e casa muito mais do
que o pretendido.

Os limites 4a e 4b — o `upper()` que casa o acento e a letra base que deixa de
casar com o acento — estão fixados por `test_regra_com_acento_casa_descricao_maiuscula`
e `test_regra_sem_acento_nao_casa_descricao_com_acento` em
`backend/tests/test_importador_regras.py`, ambos calculados à mão e com os
valores esperados escritos como constantes.

## ⚪ D9 — `detalhe-mensal` devolve HTTP 500 em mês inválido

`backend/routers/estatisticas.py:235-237` não valida as entradas:
`calendar.monthrange(13, 13)` levanta `IllegalMonthError` e `date(0, 0, 1)`
levanta `ValueError`, ambos não tratados → 500 em vez de 422. Um `mes=0` ou
`mes=13` vindo do frontend ou de um link chega ao utilizador como erro interno.

Os outros endpoints do projecto usam `Query(None, ge=1, le=12)`
(ver `routers/transacoes.py:22`), pelo que a correcção é validar as entradas
aqui e não testar o `calendar`.

**Resolvido:** `detalhe_mensal` valida as entradas com `Query` —
`backend/routers/estatisticas.py:236` (`ano: int = Query(ge=2000, le=9999)`)
e `:237` (`mes: int = Query(ge=1, le=12)`) — e responde 422 a `mes=13`,
`mes=0` e `ano=0` (testes em `backend/tests/test_api_estatisticas.py`). O
`ge=2000` alinha com `transacoes.py:22`; o `le=9999` é o teto do `date()`
(ano máximo suportado, para nunca tornar a estourar o `ValueError`). Dois
detalhes verificados com a sonda: o **erro real era sempre o `ValueError` do
`date()` da linha 240** (o `IllegalMonthError` citado acima vinha do
`calendar.monthrange` da linha 241, que nunca chegava a ser avaliado porque o
`date()` da linha anterior falha primeiro — tanto para mês fora de 1..12 como
para ano fora de 1..9999).

## ⚪ D10 — Paginação sem desempate

`backend/routers/transacoes.py:31` ordena só por `data DESC`. Transações com
a mesma data têm ordem indefinida entre páginas, pelo que a paginação pode
saltar ou repetir linhas. O `count()` e a query de itens (linhas 33-35) são
duas instruções sem snapshot partilhado, pelo que também podem discordar se
houver escrita entre elas.

Correção: `order_by(Transacao.data.desc(), Transacao.id.desc())`.

## ⚪ D11 — Dinheiro em `float` e sem verificação de finitude

`grep -n "Float\|Numeric" backend/database.py` devolve **zero `Numeric`** e 8
colunas `Float` (`database.py:144, 179, 180, 263, 264, 265, 266, 279`; a 9.ª
ocorrência é o `import` da linha 10). Todos os campos monetários e quantidades
são `float` IEEE 754, com erro de representação binária.

Os schemas Pydantic não têm `Field(..., ge=0)` nem verificação de
`NaN`/`Infinity`, pelo que ambos os valores são aceites e armazenados. Um
`NaN` num único `valor` propaga-se a todos os `SUM()` e `median()` derivados.

Os scripts de estatísticas já contornam a imprecisão com cêntimos inteiros
(`round(valor * 100)`, `estatisticas.py:164`), mas o truque tem o limite do
seu tipo: `1.005 * 100 == 100.49999999999999` em IEEE 754, e o `round()` do
Python é *banker's rounding* (arredonda para par), pelo que `round(0.125 * 100)`
dá `12` e não `13`. `Numeric(18,6)` no schema eliminaria as duas coisas de uma
vez, ao custo de converter a leitura/escrita para `Decimal`.

**Nota para os testes:** ao migrar para `Numeric`, os testes de arredondamento
mudarão de resultado, o que é esperado.

## ⚪ D12 — Assinaturas e convenções por confirmar

Itens independentes, na ordem dos ficheiros. Cada um é referenciável
isoladamente.

### Backend

- **D12a** — `routers/patrimonio.py:198` devolve `custo_total` **com sinal
  negativo** (`-custo_base`). O comentário nas linhas 189-192 regista que já
  houve bugs aqui. O frontend tem de compensar: `Ativos.jsx:182` e
  `Patrimonio.jsx:54` lêem o campo e combinam-nos. Um sinal invertido aqui
  produz totais de mais-menos-valia errados sem qualquer aviso.
- **D12b** — `routers/patrimonio.py:184-193` — `latente` é `None` quando falta
  preço, e `mais_menos_valia` degrada silenciosamente para `realizado`.
  "Sem preço" fica indistinguível de "sem mais-valia".
- **D12c** — `routers/patrimonio.py:94` e `:107` — dois `commit()` no mesmo
  endpoint (`criar_movimento`). Se o upsert de preço da linha 107 falhar, o
  movimento já foi gravado na linha 94: escrita parcial, sem rollback. Um
  `commit()` só, no fim, resolvia.
- **D12d** — `parser_importacao.py:9-22` — `_parse_valor` não tem forma de
  distinguir ponto decimal de separador de milhares. Isto **não** é um erro de
  configuração: com `separador_decimal="."`, `"1.234"` dar `1.234` é o
  comportamento correcto. O problema é o inverso — quando o ficheiro traz
  separador de milhares e o perfil não está configurado para o reconhecer, o
  valor é lido com um factor de 1000 errado, em silêncio. Não suporta
  parênteses de contabilidade (`(123,45)`) nem símbolos de moeda
  (`"1.234,56 €"`), que falham com `ErroParsing` — pelo menos esse caso é
  visível.
- **D12e** — `parser_importacao.py:107` — `fee` é somado com o sinal tal como
  vem (`valor += _parse_valor(raw_fee, ...)`). **Confirmado pelo Pedro:** no
  extracto do Trade Republic a comissão vem NEGATIVA (por exemplo `-1`). Para
  esse banco o comportamento actual é o correcto: `-50,00 + -1,00 = -51,00`, a
  comissão aumenta a saída, como deve ser. A convenção de sinal em geral continua
  por fixar — isto só seria bug com um banco que exportasse a comissão positiva,
  caso em que a comissão reduziria a saída. Não há decisão de severidade final.
  **Relevante para os testes:**
  é uma linha, e o comportamento propaga-se a `transacoes.valor` e a tudo o que
  deriva dele — taxa de poupança, estatísticas, património.
- **D12f** — `popular_bd.py:145` — `"Certificados de Aforro"` está marcado
  `tem_unidades=False`. A confirmar, sem evidência de ser erro: certificados de
  Aforro subscrevem-se por montante e o valor acumula com juros, não se
  negociam por unidades, pelo que o ramo sem unidades parece o correcto. Fica
  anotado porque a consequência é silenciosa — um certificado passa pelo
  cálculo de custo acumulado e nunca pelo FIFO. Se algum dia se registarem
  movementos parciais, há aqui uma divergência.
- **D12g** — `popular_bd.py:151-173` — `popular()` não semeia
  `SEED_TIPOS_ATIVO`, ao contrário de `routers/configuracao.py:29-39`. E o
  guard da linha 158 só olha para o número de categorias: se a BD já tiver
  categorias mas nenhum tipo de ativo, `popular()` sai sem os semear.
- **D12h** — `routers/backups.py:64` — `filename.endswith(".db")` é
  case-sensitive: um ficheiro `BACKUP.DB` é rejeitado, e a recusa não diz
  porquê.
- **D12i** — `tray.py:19` — porta `9742` hardcoded, duplicada de
  `main.PORTA` (`main.py:207`). Alterar uma e não a outra deixa a tray a
  abrir um URL morto.

### Documentação

- **D12j** — `docs/modelo-dados.md:7` — descreve `TipoAtivo` como enum
  (`etf/crypto/veiculo/imovel/outro`); em `database.py` é uma tabela, e
  `SEED_TIPOS_ATIVO` (`popular_bd.py:139`) é quem a popula.
- **D12k** — `docs/arquitectura.md:20` — descreve uma regra de caminho da BD
  anterior à actual (não menciona `RASTREIO_DB_DIR` nem a variante
  `sys.frozen`).

## ⚪ D13 — Qualidade de código (fora de âmbito por decisão)

Registado para quando se decidir introduzir linting. Não é bug.

- **Frontend:** 20 problemas do ESLint (17 erros, 3 avisos). O único que é bug
  real foi promovido a **D14**. Os restantes são: `useEffect` a chamar
  `carregar()` antes da declaração da função (7 ficheiros — `Categorias.jsx:15`,
  `Contas.jsx:14-15`, `Patrimonio.jsx:19`, `Regras.jsx:28`, `TiposAtivo.jsx:15`
  e outros), `setState` síncrono dentro de efeito (5 ficheiros), exports
  mistos num ficheiro de componente (`contexts/GuiaContext.jsx:91`), e
  variáveis não usadas (4). **Nota:** os `useEffect` que chamam `carregar()`
  antes da declaração funcionam hoje por hoisting de `function`, e o aviso do
  lint vem das regras do compilador React 19, não de um bug vivo. A correcção
  é mover a função para cima da linha do `useEffect`.
- **Backend:** sem `ruff`, sem `pyright`, sem anotações de tipo. Introduzidos
  em 2026-10-01: `pytest` + `httpx` (`backend/requirements-dev.txt`), a
  primeira suite de testes de guarda (`backend/tests/`). Lint e tipos ficam
  para quando a caracterização estiver feita.
- **N+1** em `calcular_patrimonio_em` — 1 query por conta + 2 por ativo
  (`servicos/patrimonio_serv.py:110-140`) — e sem índices em nenhuma coluna de
  data ou FK (`grep` por índices na BD actual devolve vazio). `gerar_evolucao`
  repete o cálculo completo por mês.

## 🔴 D14 — `ReferenceError` ao terminar cada importação

`frontend/src/pages/Importacao.jsx:208` chama `onDadosAlterados?.()` dentro do
`try` de `aoImportar`, mas `Importacao` não recebe essa prop: o componente é
declarado `export default function Importacao()` (linha 48), sem parâmetros.

O optional chaining não protege isto. `?.()` só evita o erro quando o
identificador **existe** e vale `null`/`undefined`; um identificador que não
existe nunca chega a ser avaliado. Confirmado em Node: `naoDeclarado?.()`
levanta `ReferenceError: naoDeclarado is not defined`.

`Transacoes` (`Transacoes.jsx:12`) e `Ativos` (`Ativos.jsx:23`) recebem a prop
com `({ onDadosAlterados })`, e `App.jsx` passa-a-lhes a todos. `Importacao` é
a única que não a recebe, apesar de `App.jsx:176` lha passar.

**Confirmado no browser.** Com o backend e o Vite a correr, e o `alert`
interceptado no Playwright: importar um CSV de 2 linhas pelo perfil
TradeRepublic deu `POST /api/importacao/importar?perfil_id=2 → 200` e o total de
transações por categorizar subiu de 0 para 1 — a importação **funcionou** — e o
utilizador viu `alert('Erro na importação.')`. A última chamada de API depois
do import não é um novo `GET /transacoes/por-categorizar/total`, ou seja, os
badges de contagem não foram actualizados.

O `catch` da linha 209 apanha o erro e mostra
`alert(...'Erro na importação.')` **depois** de a importação ter funcionado, e o
`finally` faz reset do estado como se nada tivesse acontecido. Há portanto dois
efeitos: um alerta de erro falso, e as contagens desactualizadas até recarregar
a página.

É correcção de uma linha em qualquer um dos dois lados — receber a prop no
componente, ou remover a chamada.

**Resolvido:** `Importacao` passa a receber a prop —
`frontend/src/pages/Importacao.jsx:48` (`export default function
Importacao({ onDadosAlterados })`). `App.jsx:176` já a passava; quem faltava
era o componente. O ESLint deixa de acusar `no-undef` na linha 208.

## ⚪ D19 — Leitura de CSV com delimitador diferente de vírgula

- `parser_importacao.py:_ler_linhas_csv` (aprox. linha 48) usa
  `csv.reader` sem `delimiter` (o valor por omissão é a vírgula). Num CSV
  delimitado por `;` (exportação típica do Excel em português), todo o conteúdo
  fica numa única coluna e todas as linhas que tenham dados são rejeitadas por
  `data inválida` — a falha é visível, não silenciosa. Esta situação está
  coberta pelo teste `test_csv_delimitado_por_ponto_e_virgula_e_lido_como_uma_coluna`
  em `backend/tests/test_parser_importacao.py`. Não decidido o curso de acção (se
  detectar automaticamente, permitir configuração do delimitador, ou documentar o
  requisito). ⚪

## 🟡 D20 — Despesa positiva sem a marca de reembolso desaparece dos totais

`backend/routers/estatisticas.py:268-289` (`_calculate_totals`), pelo outro lado
da D4:

```python
elif t.valor < 0 and t.categoria.tipo != receita:   # 284
    meses[chave]["despesas"] += t.valor           # 285
elif t.valor > 0 and t.reembolso:                   # 286
    meses[chave]["despesas"] += t.valor            # 287
```

Uma transação de categoria `despesa` com `valor` positivo e **sem** a marca de
reembolso não satisfaz a linha 284 (`valor < 0` falha), nem a 286 (exige a
marca), nem as duas que ficam acima (não é receita nem é investimento).
**Desaparece sem ser somada a nada** — mesma raiz da D4: nenhum ramo apanha o
caso.

Exemplo: `-45,50` seguido de `+30,00` sem marca fecham o mês com despesas
`-45,5` em vez de `-15,5`. A diferença na poupança é de 30,00, e a despesa
recuperada nunca chega a aparecer em lado nenhum.

**Comportamento esperado (decisão do Pedro):** o correcto é uma despesa positiva
estar marcada como reembolso; mas, como os valores seguem o sinal, a conta fica
certa mesmo sem a marca — somar `+30,00` às despesas de `-45,50` dá `-15,5`, que
é o valor certo. Por isso o valor **não pode ser ignorado**. Correcção: contar o
valor em despesas sempre que não case noutro ramo, o que se faz fechando a
cadeia com um ramo final em vez de a deixar terminar sem efeito.

**Por verificar (Pedro):** se existem despesas com valor positivo sem a marca nos
dados reais. Não foi consultado nenhum registo — o cenário é teórico e ficou
construído para o teste.

Fixo por `test_despesa_positiva_sem_marca_de_reembolso_desaparece` em
`backend/tests/test_estatisticas_totais.py`, que fixa o comportamento **actual**
(não o desejado), pelo que a correcção o faz falhar de propósito.

## 🟡 D15 — Sobre-venda aceite em silêncio, com o encaixe reescalado

`backend/servicos/patrimonio_serv.py:78-91` — o ciclo FIFO consome o que
houver em lotes e pára quando a lista esgota. O que sobra de `por_consumir` não
é medido, rejeitado, nem registado em lado nenhum:

```python
por_consumir = q                                    # 78
while por_consumir > 1e-9 and lotes:                 # 80
    ...
q_efetiva = q - por_consumir                        # 89
valor_efetivo = valor_m * (q_efetiva / q)           # 90
```

O `while` termina porque `lotes` esgota, não porque a quantidade bata certo, e o
encaixe é reescalado na proporção do que foi mesmo consumido. Vender 15 unidades
com 10 em carteira é, no resultado, indistinguível de ter vendido 10 por
200,00: as 5 unidades que não existiam e a parte do encaixe que lhes
corresponde desaparecem sem erro. A quantidade registada no movimento continua a
ser a que o utilizador escreveu, e não há validação que a confronte com a
posição.

**Decisão pendente (Pedro):** avisar no momento de registar a venda, ou recusar
a operação. As duas são defensáveis e divergem no que fica gravado, por isso não
se decide aqui. O teste `test_sobre_venda_escala_o_encaixe_e_nunca_avisa` fixa o
comportamento **actual**, não o desejado.

## ⚪ D16 — Bem sem unidades e sem preço desaparece do património

`backend/servicos/patrimonio_serv.py:56` — no ramo dos bens, o valor actual vem
do preço registado e não do custo:

```python
valor = round(float(preco.preco), 2) if preco else 0.0
```

Um bem com `tem_unidades=False`, com compras registadas e nenhuma linha em
`precos_ativo`, fica com `custo_base` > 0 e `valor` = 0. Continua a aparecer no
`custo_total` que o endpoint devolve, mas contribui 0 para `ativos_fisicos` e
para o `total` de `calcular_patrimonio_em`. O preço de um bem é um valor total
opcional, e nada obriga a registá-lo: o resultado é um activo que consta como
comprado e não conta para o património. Coberto por
`test_bem_sem_unidades_e_sem_preco_desaparece_do_patrimonio`.

## ⚪ D17 — Venda parcial de um bem sem unidades tratada como venda total

`backend/servicos/patrimonio_serv.py:43-47` — no ramo dos bens, qualquer
movimento do tipo `venda` desconta o custo acumulado inteiro e zera-o, sem
qualquer proporcionalidade:

```python
elif m.tipo_movimento.value == "venda":
    realizado += valor_m - custo_base
    custo_base = 0.0
    vendido = True
```

Duas compras de 10 000,00 e 5 000,00 dão `custo_base` = 15 000,00. Uma venda de
20 000,00 produz `realizado` = +5 000,00, `custo_base` = 0,0 e, por `vendido`,
`valor` = 0,0. O que se perde é a noção de que a venda foi parcial: o ramo dos
bens não tem quantidades, por isso qualquer `venda` descarrega o custo acumulado
inteiro e zera o valor. A parte do bem que ficou com o utilizador sai assim do
património com custo zero e valor zero, e o ganho foi reconhecido sobre todo o
custo e não sobre a parte vendida.

**Teórico:** este cenário não existe nos dados actuais, foi construído para o
teste. Fica registado porque o mesmo código trata a venda total e a parcial sem
distinção alguma, e o ramo não tem forma de representar uma posição parcial. É o
cenário 13 de `test_patrimonio_fifo.py`, que ficou sem etiqueta à espera de
decisão. **Decisão pendente (Pedro):** se é erro a corrigir ou convenção a
documentar.

## ⚪ D18 — Os dois pontos de entrada do cálculo escolhem preços diferentes

O mesmo activo é avaliado em dois sítios, e a escolha do preço não é a mesma:

- `backend/routers/patrimonio.py:170-175` (`resumo_ativo`) — filtra apenas por
  `ativo_id`, ordena por `data` descendente e toma o primeiro. **Não há
  limite de data**: é o preço mais recente que existir, mesmo que seja
  posterior a qualquer `data_alvo`.
- `backend/servicos/patrimonio_serv.py:133-141` (`calcular_patrimonio_em`) — o
  mesmo `order_by`, mas com `PrecoAtivoModel.data <= data_alvo`.

Para um `data_alvo` no passado, `/api/patrimonio/evolucao` usa o preço
histórico e `/api/patrimonio/ativos/{id}/resumo` mostra o de hoje. Divergem
sempre que exista um preço registado depois de `data_alvo`, e nada no endpoint
avisa que o preço é posterior ao período que o resto do ecrã representa. O
`data_preco` devolvido na linha 200 é a forma de o detectar, mas a aplicação
não o compara com nada.

Ao contrário de D3, aqui a divergência não é de *boundary* (`>` contra `>=`): um
dos lados não tem comparação nenhuma. Registado sem teste — fixá-lo exigiria
caracterizar o `/evolucao`, que está fora do âmbito desta suite.

## ⚪ D21 — `palavra_chave` vazia ou só com espaços não é validada no servidor

A palavra-chave de uma regra de categorização pode ser vazia, ou só espaços, e
nada no servidor o impede. Nenhuma das três camadas valida:

- `backend/schemas.py:57` — `palavra_chave: str`, sem `min_length`, sem
  `strip_whitespace` e sem `field_validator`;
- `backend/database.py:198` — `String(100)`, `nullable=False`, `unique=True`.
  `nullable=False` não impede `""` e `unique=True` só impede o **segundo** `""`;
- `backend/routers/regras.py:35` — a única coisa que recusa é o duplicado
  (`filter_by(palavra_chave=...)`), e só quando a palavra-chave **já** existe.
  `routers/regras.py:40-43` grava o valor tal e qual, sem cortar nem validar.

A única barreira está no formulário: `frontend/src/pages/Regras.jsx:48` faz
`if (!form.palavra_chave.trim()) return;` e a linha 51 envia o resultado de
`trim()`. É contornável com uma chamada directa à API, e o servidor não replica
a regra.

O efeito no motor é grande, porque `""` em qualquer cadeia é verdadeiro pela
definição de `in`: uma regra com palavra-chave vazia casa em **todas** as
transações e passa a categorizá-las todas com a sua categoria. Uma palavra-chave
só com espaços é mais discreta e mais difícil de notar, porque `"   "` não casa
em `""` mas casa em qualquer descrição que tenha três espaços seguidos.

**Decisão pendente (Pedro):** validar no schema, no motor, ou nos dois. As três
são defensáveis e não são equivalentes — no schema fecha-se a entrada pela API e
ficam de fora as linhas `importador_transacoes.py:10` e `:17`; no motor trata-se
de uma guarda nas duas fases; nos dois, a palavra-chave vazia deixa de ser um
caso limite com significância. **Não decidido aqui.**

Fixo por `test_palavra_chave_vazia_casa_em_tudo` em
`backend/tests/test_importador_regras.py`, que fixa o comportamento **actual**
(não o desejado): uma regra vazia com `categoria_id` 1 transforma
`"TRANSFERENCIA PARA O TB"` em `(1, 10)`. Se a D21 for decidida no sentido de
validar `palavra_chave`, o teste passa a falhar de propósito.

**Resolvido:** validação **só no schema da entrada** —
`RegraCreate.palavra_chave` (`backend/schemas.py:62`) é
`Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]`.
`RegraBase` e `Regra` ficam sem a restrição, para que uma regra antiga com
palavra-chave vazia na BD continue a ser lida pela listagem (ver a guarda
`test_listagem_continua_a_ler_regra_antiga_com_palavra_chave_vazia`). A via
`POST /api/regras/` passa a responder 422 a `""` e `"   "`, e guarda
`"  PINGO  "` como `PINGO` (testes em `backend/tests/test_api_regras_criar.py`).
**O motor não mudou:** `aplicar_regras` (`importador_transacoes.py:10` e `:17`)
continua sem guarda, e por isso `test_palavra_chave_vazia_casa_em_tudo`
continua a passar — a frase acima ("o teste passa a falhar de propósito") só
valeria se a validação tivesse sido também no motor. A barreira `trim()` do
formulário (`Regras.jsx:48` e 51) mantém-se.

---

## Regra a seguir

Ao corrigir qualquer item, no mesmo commit, corrige o código, ajusta ou
acrescenta o teste que o fixa, e marca o item como **Resolvido**. Assim a
mudança fica explícita no histórico em vez de ser um efeito colateral.
