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

Os itens já resolvidos têm « — resolvido» no título.

Os itens `D12a`…`D12k` são pontos independentes dentro do mesmo ficheiro,
separados para que o `grep` por `D12e` aponte para um só sítio.

---

## 🔴 D1 — Chaves estrangeiras não são forçadas pelo SQLite — resolvido

`backend/database.py` criava a engine sem `PRAGMA foreign_keys=ON`, e não há
`ON DELETE` nem cascade nas `ForeignKey` declaradas
(`database.py:178, 195-198, 210-211, 247, 255, 270-271, 288`). O SQLite não
aplica chaves estrangeiras por omissão, e as `relationship()` também não
declaram `cascade` (`database.py:169, 262-263`).

Na prática, apagar uma categoria **pode** deixar as transações a apontar para
linhas que já não existem, sem erro. Essas transações desapareceriam das
estatísticas (os joins são `INNER`), apareceriam sem nome na listagem, e só
seriam contadas em `/transacoes/por-categorizar/total` se não tivessem
subcategoria (o filtro é `categoria_id IS NULL OR subcategoria_id IS NULL`, e
o `categoria_id` órfão não é NULL).

**O que os testes de caracterização mediam antes da política de apagar** (ver
a secção «Política de apagar», mais abaixo):

- `test_apagar_categoria_com_subcategorias_integrity` — apagar uma categoria
  **com** subcategorias dá `IntegrityError` (`NOT NULL constraint failed:
  subcategorias.categoria_id`) e, em produção, **500**, mesmo com as chaves
  estrangeiras desligadas: sem `ON DELETE` nem `cascade`, o SQLAlchemy tenta
  desassociar as subcategorias pondo `subcategorias.categoria_id` a `NULL`, e a
  coluna é `NOT NULL` (`database.py:178`).
- `test_apagar_categoria_deixa_transacao_orfa` — apagar uma categoria só com
  transacções directas dá **200** e deixa `transacoes.categoria_id` pendente.
  É este o caso que passaria a falhar se a pragma fosse ligada.
- `test_apagar_subcategoria_desassocia_transacoes` — apagar uma subcategoria com
  transacções dá **200** e põe `transacoes.subcategoria_id` a `NULL` (coluna
  `nullable=True`, `database.py:196`), mantendo a categoria.

### 🔴 D1a — O schema da BD actual aponta para uma tabela que não existe — resolvido

Isto não é hipotético, é o estado actual, e só apareceu com
`PRAGMA foreign_key_check` (consulta que compara as *definições* das chaves, ao
contrário de um `JOIN`, que não encontra a tabela e por isso reporta zero).

`precos_ativo` e `movimentos_ativo` têm `FOREIGN KEY(ativo_id) REFERENCES
"ativos_old" (id)`, e **`ativos_old` não existe**. A tabela `ativos` existe e
está preenchida (5 linhas, 19 preços, 41 movimentos; 18 preços em 2026-10-19), mas nenhuma referência
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

**Resolvido.** Não com um script manual, porque os backups antigos têm o mesmo
schema e o restauro substitui o ficheiro inteiro: a correcção é
`reparar_fk_ativos()` em `backend/database.py`, chamada por `criar_tabelas()`
(no arranque, em dev e no executável) e por `importar_backup` depois da troca
(`backend/routers/backups.py`). Se nenhum DDL mencionar `ativos_old`, não
escreve nada. Se mencionar, recria cada tabela com o seu próprio DDL, mudando
só a referência, numa transacção, e compara as linhas antes e depois; segue o
procedimento da documentação do SQLite (só a tabela nova é renomeada, e nada
aponta para ela), pelo que não depende da regra de reescrita do `RENAME` que
partiu o schema. Uma falha no restauro repõe a BD anterior; uma falha no
arranque impede a app de arrancar, sem mexer nos dados. Quando repara, escreve
no log a versão do SQLite em uso, o que responde à linha «por confirmar» da
tabela abaixo.

Ensaiado numa cópia da BD real: as 11 tabelas com as mesmas contagens e o
mesmo conteúdo, `foreign_key_check` de 59 violações para 0, `integrity_check`
`ok`. Testes em `backend/tests/test_reparar_fk_ativos.py` (a fixture
`criar_bd_com_fk_partida`, no `conftest.py`, reproduz a migração que partiu o
schema) e, para o restauro e o arranque, no fim de
`backend/tests/test_backups/test_importar.py`.

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
ambiente. O executável distribuído não usa a CLI nem o `venv`, mas a
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
  qualquer pré-checagem. **Já falha hoje, sem a pragma**, quando a categoria
  tem subcategorias (500 por `NOT NULL constraint failed:
  subcategorias.categoria_id`); se só tiver transacções directas devolve **200**
  e deixa-as órfãs, e só nesse caso a pragma a faria falhar (ver os testes
  acima).
- `apagar_subcategoria` (`routers/categorias.py:91`) — idem, sem pré-checagem.
  **Passa a falhar.**
- `apagar_ou_desativar_conta` (`routers/contas.py:40-52`) — **já faz
  pré-checagem**: se houver transações, desactiva a conta em vez de a apagar
  (linha 49). Não é afectado.
- `apagar_tipo_ativo` (`routers/tipos_ativo.py:35-41`) — **já faz
  pré-checagem** (`if tipo.ativos` na linha 39 devolve 409). Mas
  `ativos.tipo_id` é `NOT NULL`, e a pré-checagem só protege se a lista
  `tipo.ativos` estiver carregada e em dia. Fixo por
  `test_apagar_tipo_ativo_com_ativos_da_409` em
  `backend/tests/test_api_tipos_ativo.py`.

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
pool recicla). A D1a já está corrigida; falta decidir a política de
`ON DELETE`, porque `ON DELETE CASCADE` muda o comportamento dos endpoints.

### Política de apagar — decidida e aplicada na aplicação

**Decisão do utilizador:**

- uma **categoria com transações** (directas, ou nas suas subcategorias) não se
  apaga: 409 «A categoria tem N transações; muda-as de categoria antes de a
  apagar.»;
- uma **categoria sem transações** apaga-se com as suas subcategorias e com as
  regras que apontam para ela ou para elas;
- uma **subcategoria** apaga-se; as suas transações ficam por categorizar na
  mesma categoria, e as regras que apontavam para ela ficam sem subcategoria.

Aplicada em `apagar_categoria` e `apagar_subcategoria`
(`backend/routers/categorias.py`), e a página Categorias passou a mostrar o
erro (antes, apagar uma categoria com subcategorias dava 500 e o ecrã não
fazia nada). Fica nas «Decisões de design» do `README.md`. Testes em
`backend/tests/test_api_categorias.py`: os dois de caracterização foram
substituídos por `test_apagar_categoria_com_transacoes_da_409_e_nada_muda`,
`test_apagar_categoria_sem_transacoes_leva_subcategorias_e_regras` e
`test_apagar_categoria_conta_transacoes_das_suas_subcategorias`, e
`test_apagar_subcategoria_desassocia_transacoes` passou a verificar a regra.

### Resolvido

**Decisão do utilizador:** ligar a pragma e **não declarar `ON DELETE`** (fica
o `NO ACTION` do SQLite, que recusa). A política de apagar continua nos
handlers, e a BD é a rede de segurança: um esquecimento num endpoint, um
script de migração ou uma edição à mão passam a falhar em vez de deixarem
órfãos. Foram afastados o `CASCADE` (um esquecimento apagaria transações) e o
`SET NULL` (apagaria a categoria das transações e, em `regras.categoria_id`,
transformaria a regra numa regra de exclusão; nas colunas `NOT NULL` nem é
possível). Ambos obrigariam também a recriar tabelas na BD real e nos backups,
porque o SQLite não altera o `ON DELETE` de uma chave existente; a pragma não
mexe no ficheiro.

- `ligar_chaves_estrangeiras` (`backend/database.py`) faz
  `PRAGMA foreign_keys = ON` em cada conexão nova da engine, por
  `event.listen(engine, "connect", ...)`. O `conftest.py` liga-a também na
  engine in-memory dos testes, pelo que a suite inteira corre com a pragma.
  `reparar_fk_ativos` continua a desligá-la na sua própria conexão `sqlite3`.
- Os `DELETE` não mudam: todos tratam os filhos antes do pai (categorias e
  subcategorias pela política acima, `tipos_ativo` com 409, `ativos` apagando
  movimentos e preços, `contas` desactivando ou, sem transações, deixando os
  perfis sem conta pela `relationship`).
- **Encontrado ao ensaiar:** oito escritas aceitavam um ID inexistente e
  criavam órfãos com a pragma desligada (com ela, dariam 500).
  **Decisão do utilizador:** validar em cada handler, com a mensagem do
  padrão existente:
  - `PUT /transacoes/{id}` com `categoria_id` → 400 «Categoria não encontrada.»;
  - `POST /regras` com `categoria_id` ou `subcategoria_id` → 400 «Categoria /
    Subcategoria não encontrada.»;
  - `POST /patrimonio/ativos` com `tipo_id` → 404 «Tipo de ativo não
    encontrado.» (antes gravava o ativo órfão **e** respondia 500, porque a
    resposta `schemas.Ativo` exige o tipo);
  - `POST /patrimonio/movimentos` com `transacao_id` → 404 «Transação não
    encontrada.»;
  - `POST`, `PUT` e `PATCH .../conta` de `/perfis-importacao` com `conta_id` →
    400 «Conta não encontrada.» (`_validar_conta`).

Testes: `backend/tests/test_chaves_estrangeiras.py` (a engine da app liga a
pragma; a BD recusa apagar um pai com filhos e gravar um filho sem pai), um
teste por escrita validada nos ficheiros de cada router,
`test_apagar_conta_sem_transacoes_desassocia_os_perfis` em
`test_api_contas.py`, e o de caracterização
`test_associar_conta_inexistente_grava_por_fk_desligada` invertido para
`test_associar_conta_inexistente_da_400_e_nao_grava`. Verificados por
mutação: 12 mutantes, todos mortos.

Fica de fora, por não ser uma chave estrangeira: nada impede uma transação ou
uma regra com uma subcategoria que não pertence à sua categoria (ver D8 a).
`POST /regras` não o verifica; `PUT /transacoes/{id}` e `aplicar-em-massa`
verificam.

## 🟡 D2 — `total` do património não bate com a soma dos componentes — resolvido

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

**Resolvido:** `calcular_patrimonio_em` (`backend/servicos/patrimonio_serv.py:152-162`)
arredonda primeiro os três componentes e o `total` é a soma desses valores
arredondados, outra vez arredondada a 2 casas para tirar o ruído de vírgula
flutuante (`0.1 + 0.2`). Face ao que era apresentado, o `total` muda no
máximo 2 cêntimos (cada componente arredondado desvia até meio cêntimo), e
passa a bater sempre com a soma das três séries do gráfico. O teste de caracterização foi invertido
(`test_evolucao_total_e_a_soma_dos_componentes_arredondados`: total 0.02 em vez
de 0.01) e há um teste novo para o ruído,
`test_evolucao_total_sem_ruido_de_virgula_flutuante`, ambos em
`backend/tests/test_api_patrimonio.py`. A passagem a `Decimal` fica para a D11
(resolvida sem mudar o tipo das colunas; ver lá).

## 🟡 D3 — Boundary de data de referência diverge entre dois endpoints — resolvido

A mesma conta é calculada de duas maneiras incompatíveis:

- `backend/servicos/patrimonio_serv.py:112` — `Transacao.data > conta.data_referencia`
- `backend/routers/contas.py:62` — `data >= :data_referencia`

Uma transação exactamente na data de referência entra no saldo de
`/api/contas/{id}/saldo` e não entra no `/api/patrimonio/evolucao`. O
utilizador vê dois saldos diferentes para a mesma conta.

É uma decisão de negócio, não um erro evidente: "saldo de referência" pode
significar "antes desta data" ou "até esta data, exclusive". Tem de ser
escolhido um dos dois e propagado.

**Resolvido (decisão do utilizador: o saldo de referência é o do fim do
dia):** já reflecte as transacções desse dia, que por isso não se somam outra
vez. `backend/routers/contas.py:62` passou de `>=` para `>`, igual a
`servicos/patrimonio_serv.py:112`; na página Património, o cartão Liquidez e a
linha do gráfico passam a concordar. Verificado numa cópia da BD real (aberta
só em leitura e apagada a seguir): nenhuma das duas contas tem transacções no
dia de referência, ambas as datas são anteriores a todas as transacções, e o
saldo de referência do ActivoBank bate ao cêntimo com o saldo do banco da
primeira transacção (14 818,96 + 804,50 = 15 623,46). A mudança não altera
nenhum número actual. O teste de caracterização foi invertido
(`test_saldo_conta_e_evolucao_excluem_a_data_de_referencia`, saldo 130,0 em vez
de 180,0, em `backend/tests/test_api_contas.py`).

## 🟡 D4 — Receita negativa desaparece de todos os totais — resolvido

`backend/routers/estatisticas.py:272-293` (`_calculate_totals`):

```python
if t.categoria.tipo == receita and not t.reembolso and t.valor > 0:  # 284
elif t.categoria.tipo == investimento:                               # 286
elif t.valor < 0 and t.categoria.tipo != receita:                    # 288
elif t.valor > 0:                                                    # 290
```

Os números são das linhas da condição; a soma correspondente está logo a seguir,
nas linhas 285, 287, 289 e 291.

Uma transação de categoria `receita` com `valor` negativo (estorno, devolução
de receita recebida) não satisfaz a linha 284 (`valor > 0` falha), nem a 288
(exclui explicitamente receitas). Não cai em nenhuma branch: **desaparece sem
ser somada a nada**, e o mês fecha sem esse valor.

**Resolvido (decisão do utilizador: o sinal manda, como na D20):** um ramo novo
em `_calculate_totals` (`backend/routers/estatisticas.py:284-286`) soma a
receita negativa às `receitas`, com o sinal que tem: um estorno de -300,00 num
mês com 1500,00 de salário fecha com receitas 1200,0. A marca de reembolso não
muda nada numa receita negativa (só desvia as receitas **positivas** para as
despesas). Só o resumo mensal é afectado (receitas, poupança e taxa de
poupança): as vistas por categoria somam por SQL e já incluíam o valor. O teste
de caracterização foi invertido (`test_receita_negativa_reduz_as_receitas`) e há
um novo para a marca
(`test_receita_negativa_marcada_como_reembolso_tambem_reduz_as_receitas`),
ambos em `backend/tests/test_estatisticas_totais.py`.

## 🟡 D5 — Transferências contaminam o denominador das médias do `/por-categoria` e do `/resumo-mensal` — resolvido

`backend/routers/estatisticas.py:59-65` conta os meses distintos numa query
que **não** exclui transferências; a query de totais do `/por-categoria`
(`linha 67+`) exclui (`Categoria.tipo != transferencia`, linha 77).

Consequência: meses em que houve apenas transferências entram no denominador
sem entrarem no numerador, pelo que **as médias mensais do `/por-categoria`
são sistematicamente baixas** — a da categoria (linha 111) e a das
subcategorias (linha 117). Só `/por-categoria` calcula médias e medianas:
`/por-subcategoria` só soma totais em cêntimos (linhas 164-166) e não tem
médias nem medianas.

Sobre o preenchimento com zeros: as duas médias dividem por `meses_distintos`
(linhas 111 e 117), e o `[0] * (meses_distintos - len(...))` das linhas 109 e
115 soma zeros, que não alteram o `sum()`. **O preenchimento é código morto**
— sem ele, `sum(totais) / meses_distintos` é exactamente o mesmo. As medianas
(linhas 110 e 116) usam a lista sem preenchimento.

O `/resumo-mensal` tem a mesma raiz: `todos_meses` (linhas 16-19) lista os
meses distintos sem excluir transferências, e as linhas 23-26 acrescentam os
meses só com transferências a zeros — a média (linha 47) e a mediana (linha
48) de `totais_despesas` contam com eles.

Fixo por `test_por_categoria_media_com_zeros_e_mediana_sem_preenchimento` e
`test_resumo_mensal_agrega_por_mes_e_calcula_poupanca_media_e_mediana` em
`backend/tests/test_api_estatisticas.py`, que fixam o comportamento actual com
os valores calculados à mão; corrigir o denominador fazê-los-á falhar de
propósito.

**Resolvido (decisão do utilizador: convenção, sem mudar os números):** o
fluxo pretendido é categorizar as transacções logo a seguir a importá-las, pelo
que um mês só por categorizar dura minutos, e um mês só com transferências não
acontece na prática. O comportamento fica como está e foi registado como
convenção nas «Decisões de design» do `README.md`. O preenchimento com zeros,
que era código morto, saiu de `por_categoria` num commit `refactor` à parte, e
os testes existentes continuaram a passar sem mudar nenhum valor. Os dois
testes acima deixaram de ter a etiqueta D5 e apontam para o README.

## 🔴 D6 — Restauro de backup valida só 3 das 11 tabelas — resolvido

### Descrição original

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

Resultado: um backup antigo ou de outra instalação era aceite, o `.anterior` de
segurança era apagado no fim do restauro e o património inteiro — movimentos e
preços — desaparecia sem qualquer aviso. Como o `.anterior` só se apagava
*depois* de tudo confirmar, e a confirmação era fraca, não havia forma de
recuperar.

A lista das tabelas esperadas estava fixada por testes de caracterização
(`backend/tests/test_backups/`) com os nomes reais do modelo. Esses testes não
garantiam a derivação automática da lista: quando `TABELAS_ESPERADAS` passasse
a derivar de `Base.metadata.sorted_tables` (fonte de verdade), os testes de
caracterização iriam falhar de propósito, para serem invertidos.

**O que os testes mediram antes da correção:** para um `.db` que contém apenas
as 3 tabelas esperadas (sem as restantes 8), o endpoint devolvia
`200 {"ok": true, "mensagem": "Base de dados restaurada"}` e, ao ler uma tabela
que não existe no novo estado (exemplo: `ativos`), o acesso levantava
`OperationalError: no such table: ativos`. Este é o mesmo defeito que estava
anotado como `xfail` no commit 398130b.

### Resolvido

- `backend/routers/backups.py:16` — `TABELAS_ESPERADAS` deriva de
  `Base.metadata.sorted_tables` (as 11 tabelas do modelo, fonte de verdade): um
  backup a que falte qualquer tabela do modelo é rejeitado com 400.
- `backend/routers/backups.py:71-99` — `_validar_estrutura` nova. Compara as
  tabelas reais com `TABELAS_ESPERADAS` e, tabela a tabela, as **colunas** do
  modelo contra o backup. O ficheiro é aberto só em leitura
  (`Path(path).resolve().as_uri() + "?mode=ro"`, linha 79) para nunca escrever
  no ficheiro a validar. Tabelas e colunas **a mais** são aceites — apenas a
  falta rejeita.
- `backend/routers/backups.py:20` — falha de estrutura responde sempre 400 com
  a mensagem única `"O ficheiro não corresponde a um backup válido do
  Rastreio-DB"` (`MENSAGEM_ESTRUTURA`): por decisão do utilizador, o erro não diz o
  que falta (não expõe o esquema interno).
- `backend/routers/backups.py:124-131` — validação ANTES de tocar no DB: a
  validação antiga (`_validar_sqlite`, linhas 49-68) e a nova
  (`_validar_estrutura`) correm sobre o `.tmp` já gravado; em caso de rejeição
  o `.tmp` é removido.
- `backend/routers/backups.py:143-144` — verificação pós-troca usa a **mesma**
  `_validar_estrutura` sobre o `DB_PATH`, no lugar dos três `SELECT COUNT(*)`.
- O `.anterior` **nunca é apagado automaticamente**: a limpeza inicial
  (`backups.py:114-117`) remove só o `.tmp`; no sucesso o `.anterior` fica no
  disco (`backups.py:159-160`) até o restauro seguinte o substituir
  (`shutil.copy2`, linha 137); no rollback (`backups.py:150-151`) a BD é
  reposta a partir do `.anterior` e ele permanece (deixou de haver o
  `os.remove`).
- `backend/routers/backups.py:146-157` — o bloco `except Exception` continua a
  devolver 500 (linha 157), sem tocar no `.anterior`.
- `backend/tests/test_backups/test_importar.py` — caracterização invertida e
  testes novos: validação exaustiva por tabela
  (`test_ficheiro_sem_uma_tabela_do_modelo_e_sempre_rejeitado`), coluna em
  falta (`test_coluna_em_falta_numa_so_tabela_e_rejeitado`), rejeição que não
  toca num `.anterior` pré-existente, modelo completo com coluna extra aceite,
  e `test_a_lista_validada_e_a_do_modelo`, que garante que a lista vem do
  modelo — se a fonte de verdade mudar, o teste falha de propósito.

**O que continua por cobrir:** o rollback (linhas 146-155) e a verificação
pós-troca (linha 144) não são atingíveis com os ficheiros construídos nos
testes: a validação pós-troca corre sobre um ficheiro que acabou de passar a
validação prévia e o `os.replace` é atómico, por isso o ramo não falha de forma
natural. O docstring de `backend/tests/test_backups/test_importar.py` mantém
«Rollback por cobrir» com essa justificação.

## 🟡 D7 — Precedência das regras de categorização é não determinística — resolvido

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

**Resolvido (decisões do utilizador):**

- **Ordem:** `regras_por_precedencia` (`backend/importador_transacoes.py`)
  ordena as regras pela palavra-chave mais longa primeiro (a mais específica)
  e, em empate, pela mais antiga (`id` menor). É usada na importação e na
  pré-visualização da aplicação em massa (`routers/regras.py`), que deixam de
  depender da ordem em que o SQLite devolve as linhas.
- **`break`:** mantém-se: a primeira regra que casa decide sozinha, mesmo que
  deixe a subcategoria por preencher. Na importação, o caso «casou mas não
  atribuiu» nunca acontece (as transacções são novas e não têm categoria); o
  caso que acontece é uma regra seguinte da mesma categoria que traria a
  subcategoria, e a ordem nova já resolve o mais comum (palavras-chave contidas
  uma na outra, como `MERCADO` / `MERCADO CENTRAL`).

As duas regras ficaram nas «Decisões de design» do `README.md`. Testes novos:
`test_importar_avalia_primeiro_a_palavra_chave_mais_longa` e
`test_importar_com_o_mesmo_comprimento_ganha_a_regra_mais_antiga`
(`backend/tests/test_importador_regras.py`) e
`test_pre_visualizar_avalia_primeiro_a_palavra_chave_mais_longa`
(`backend/tests/test_api_regras_geral.py`). Os três testes do `break` deixaram
de ter a etiqueta D7 e apontam para o README.

## 🟡 D8 — Motor de regras duplicado com semântica divergente — resolvido

A mesma lógica de duas fases existe em três sítios:

| Sítio | Correspondência |
|---|---|
| `importador_transacoes.py:5` (`aplicar_regras`) | `palavra_chave.upper() in descricao.upper()` |
| `routers/regras.py:94` (`pre_visualizar_regras`) | igual, mas pré-filtra `subcategoria_id IS NULL` (linha 88) |
| `routers/regras.py:54` (`criar_regra`, backfill) | SQL `ilike` — **ASCII-only** |

Consequências:

- (a) o preview (`pre_visualizar_regras`, `routers/regras.py:85`) e o backfill
  (`criar_regra`, `routers/regras.py:34`) **contam o mesmo** com dados válidos.
  Os dois conjuntos só divergem no estado órfão — `categoria_id` a NULL com
  `subcategoria_id` definida: a 1.ª query do backfill (`regras.py:52-55`) filtra
  só `categoria_id == None` e apanha-o, enquanto a pré-visualização pré-filtra
  `subcategoria_id IS NULL` (`regras.py:87-89`) e descarta-o. As chaves
  estrangeiras não impedem esse estado (a subcategoria existe), mesmo com a D1
  resolvida; chega à BD por edição directa. Fixado por
  `test_pre_visualizar_e_backfill_contam_o_mesmo_com_dados_validos` e
  `test_backfill_sobre_transacao_orfa_sobrescreve_a_subcategoria` em
  `backend/tests/test_api_regras_geral.py`.
- (b) `ilike` não casa acentos, `upper()` casa — uma regra com "ç" funciona na
  importação e não no backfill. Fixado, no motor, por
  `test_regra_com_acento_casa_descricao_maiuscula` e
  `test_regra_sem_acento_nao_casa_descricao_com_acento` (ver abaixo) e, no
  backfill, por `test_backfill_com_acento_nao_casa_descricao_maiuscula` em
  `backend/tests/test_api_regras_geral.py`.
- (c) `palavra_chave` com `%` ou `_` é injectado como wildcard no `ilike`
  (linha 54) e casa muito mais do que o pretendido. Fixado por
  `test_backfill_percent_e_wildcard` e `test_backfill_underscore_e_wildcard`
  em `backend/tests/test_api_regras_geral.py`.

Os limites 4a e 4b — o `upper()` que casa o acento e a letra base que deixa de
casar com o acento — estão fixados por `test_regra_com_acento_casa_descricao_maiuscula`
e `test_regra_sem_acento_nao_casa_descricao_com_acento` em
`backend/tests/test_importador_regras.py`, ambos calculados à mão e com os
valores esperados escritos como constantes.

**Resolvido (decisão do utilizador: o backfill igual à importação, com
exclusões):**

- `casa_palavra` (`backend/importador_transacoes.py`) é a comparação única:
  `palavra_chave.upper() in descricao.upper()`, que ignora maiúsculas também
  nas letras acentuadas e trata a palavra-chave como texto literal. Usam-na a
  importação (`aplicar_regras`), a pré-visualização e o backfill de
  `criar_regra` (`backend/routers/regras.py`);
- o backfill deixou de usar `ilike`: filtra em Python, pelo que (b) os acentos
  casam e (c) `%` e `_` são texto;
- o backfill passou a respeitar as regras de exclusão (`categoria_id` nulo),
  como a importação: uma transacção que uma exclusão apanha não é tocada. Esta
  divergência não estava listada acima e foi encontrada ao corrigir o item;
- (a) a diferença do pré-filtro só existe com transacções órfãs, um estado que
  as chaves estrangeiras não impedem; os testes que a fixam tiveram a etiqueta
  D1 até a D1 ser resolvida.

Verificado numa cópia da BD real (só leitura, apagada a seguir): 58 regras,
nenhuma com acentos, `%` ou `_`, e o `ilike` e o `upper()` davam o mesmo
resultado em todos os pares (regra, transacção); há uma regra de exclusão
(`TRF`) e 4 transacções que casam com ela e com uma regra de categoria, que
um backfill futuro passa a deixar por tocar. Os testes de caracterização foram
invertidos (`test_backfill_com_acento_casa_descricao_maiuscula`,
`test_backfill_percent_e_texto_literal`,
`test_backfill_underscore_e_texto_literal`) e há um novo,
`test_backfill_respeita_as_regras_de_exclusao`, em
`backend/tests/test_api_regras_geral.py`.

Fica de fora: a pesquisa por descrição da listagem de transacções
(`routers/transacoes.py`, `ilike`) continua só ASCII; não faz parte do motor de
regras e foi registada como D28.

## ⚪ D9 — `detalhe-mensal` devolve HTTP 500 em mês inválido — resolvido

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

## ⚪ D10 — Paginação sem desempate — resolvido

`backend/routers/transacoes.py:31` ordena só por `data DESC`. Transações com
a mesma data têm ordem indefinida entre páginas, pelo que a paginação pode
saltar ou repetir linhas. O `count()` e a query de itens (linhas 33-35) são
duas instruções sem snapshot partilhado, pelo que também podem discordar se
houver escrita entre elas.

Correção: `order_by(Transacao.data.desc(), Transacao.id.desc())`.

**Resolvido (ordenação):** `backend/routers/transacoes.py:31` ordena agora por
`Transacao.data.desc(), Transacao.id.desc()`: dentro da mesma data, a
transacção com `id` mais alto vem primeiro, e a ordem é a mesma em todas as
páginas. Teste novo em `backend/tests/test_api_transacoes.py`:
`test_listar_paginacao_desempata_mesma_data_por_id_desc` (quatro transacções na
mesma data repartidas por três páginas de 2, sem repetir nem saltar ids). Os
dois testes que tinham a etiqueta D10 deixaram de a ter.

**Limitação aceite (decisão do utilizador):** o `count()` e a query de itens
(`transacoes.py:54-55`) continuam a ser duas leituras separadas. Só discordam
se houver uma escrita entre as duas (por exemplo, uma importação noutro
separador), e o efeito é o `total` não bater certo com os itens até ao pedido
seguinte. Numa app local de um só utilizador não justifica mexer na forma como
a sessão SQLite abre transacções.

## ⚪ D11 — Dinheiro em `float` e sem verificação de finitude — resolvido

`grep -n "Float\|Numeric" backend/database.py` devolve **zero `Numeric`** e 8
colunas `Float` (`database.py:155, 190, 191, 274, 275, 276, 277, 290`; a 9.ª
ocorrência é o `import` da linha 12). Todos os campos monetários e quantidades
são `float` IEEE 754, com erro de representação binária.

Os schemas Pydantic não têm `Field(..., ge=0)` nem verificação de
`NaN`/`Infinity`, pelo que ambos os valores são aceites e armazenados. Um
`NaN` num único `valor` propaga-se a todos os `SUM()` e `median()` derivados.

Os scripts de estatísticas já contornam a imprecisão com cêntimos inteiros
(`round(valor * 100)`, `estatisticas.py:173` e `:236`), mas o truque tem o limite do
seu tipo: `1.005 * 100 == 100.49999999999999` em IEEE 754, e o `round()` do
Python é *banker's rounding* (arredonda para par), pelo que `round(0.125 * 100)`
dá `12` e não `13`. `Numeric(18,6)` no schema eliminaria as duas coisas de uma
vez, ao custo de converter a leitura/escrita para `Decimal`.

**Nota para os testes:** ao migrar para `Numeric`, os testes de arredondamento
mudarão de resultado, o que é esperado.

**O que se verificou** (numa cópia da BD real, aberta só em leitura): o
`Numeric` não teria resolvido nada no armazenamento, porque o SQLite não tem
tipo decimal e uma coluna `NUMERIC` continua a guardar `REAL`. Todas as
transacções, saldos e valores totais têm no máximo 2 casas, e com 2 casas a
conversão para cêntimos dá sempre o número certo. O erro que se via era outro,
o dos empates no meio cêntimo, cujo sentido ficava ao acaso do binário: das
médias e medianas dos dados reais, seis vinham 1 cêntimo ao lado (por
exemplo Entretenimento em 2025: (-96,70 - 62,99) / 2 = -79,845 aparecia
-79,84). Não havia valores não finitos, mas um `NaN` numa
coluna obrigatória dava 500, numa opcional (`quantidade`) era gravado como
NULL em silêncio, e um `Infinity` num preço era gravado e deixava o resumo do
ativo e a evolução do património a dar 500. O parser de importação aceitava
`"nan"`, `"inf"` e `"1e400"`.

**Resolvido (decisões do utilizador: as colunas continuam `REAL`, o
arredondamento é ao cêntimo com a metade para longe de zero, os valores não
finitos são recusados à entrada, e quantidades e preços mantêm a precisão com
que foram introduzidos):** não há mudança de schema nem migração da BD ou dos
backups.

- `backend/servicos/dinheiro.py` tem o arredondamento único: `exato` lê o
  float pelo valor escrito (`Decimal(repr(x))`) e `arredondar` arredonda ao
  cêntimo com `ROUND_HALF_UP`, como o ARRED do Excel. Substitui os
  `round(..., 2)` das estatísticas, do saldo da conta, do resumo do ativo e da
  evolução do património, e os cêntimos inteiros passam a
  `round(arredondar(r.valor) * 100)`.
- As médias e medianas das estatísticas são calculadas em `Decimal`, e o FIFO
  de `_resumo_valor_ativo` também: cada lote guarda o custo total e o custo
  vendido multiplica antes de dividir. O valor de um ativo com unidades é
  `quantidade x preço` em `Decimal`. A função continua a devolver floats.
- Os campos numéricos dos schemas passaram a `FiniteFloat`, e o
  `_parse_valor` recusa um valor não finito como «valor inválido». Pela API,
  um `NaN` ou `Infinity` escrito à mão no JSON dá 500 e não 422, porque o
  handler de validação do FastAPI repete o valor no corpo do erro e o JSON não
  o aceita; nada é gravado. Pelo browser não acontece: `JSON.stringify(NaN)`
  dá `null`, que dá 422.

Comparadas todas as respostas de leitura (estatísticas, património, saldos)
numa cópia da BD real, antes e depois, mudam só esses seis valores, todos
empates exactos no `/por-categoria`: em 2024, as médias de Restauração
(-155,48 / 8 = -19,435 -> -19,44) e de Portagens (-88,36 / 8 = -11,045 ->
-11,05); em 2025, as medianas de Entretenimento (-79,845 -> -79,85),
Transporte (-108,565 -> -108,57), Salário (854,155 -> 854,16) e Portagens
(-33,365 -> -33,37). Os zeros de algumas médias e totais passam de `0` a
`0.0` no JSON, que é o mesmo número para o frontend. O
teste de caracterização foi invertido
(`test_arredondamento_em_centimos_arredonda_meio_centimo_para_longe_de_zero`,
13 cêntimos em vez de 12, em `backend/tests/test_estatisticas_totais.py`), e
há testes novos em `test_dinheiro.py`, `test_api_estatisticas.py`,
`test_patrimonio_fifo.py` (cenários 22 e 23), `test_api_patrimonio.py` e
`test_parser_importacao.py`.

## ⚪ D12 — Assinaturas e convenções por confirmar — resolvido

Itens independentes, na ordem dos ficheiros. Cada um é referenciável
isoladamente.

### Backend

- **D12a — resolvido** — `routers/patrimonio.py:198` devolve `custo_total` **com sinal
  negativo** (`-custo_base`). O comentário nas linhas 189-192 regista que já
  houve bugs aqui. O frontend tem de compensar: `Ativos.jsx:182` e
  `Patrimonio.jsx:54` lêem o campo e combinam-nos. Um sinal invertido aqui
  produz totais de mais-menos-valia errados sem qualquer aviso.
  **Resolvido (decisão do utilizador: convenção):** o `custo_total` continua
  negativo, coerente com as transacções, e é assim que a página Ativos o mostra.
  A regra ficou escrita em `docs/modelo-dados.md` («Convenções de sinal»), com
  um comentário no sítio onde é produzido (`routers/patrimonio.py`, no
  `resumo_ativo`) e onde o frontend depende dele (`Patrimonio.jsx`, no
  `totalMaisValia`). Os testes de `test_patrimonio_fifo.py` deixaram de citar a
  D12a e apontam para a convenção.
- **D12b — resolvido** — `routers/patrimonio.py:184-193` — `latente` é `None` quando falta
  preço, e `mais_menos_valia` degrada silenciosamente para `realizado`.
  "Sem preço" fica indistinguível de "sem mais-valia".
  **Resolvido (decisão do utilizador: só no ecrã):** a API não mudou. Na página
  Ativos (`frontend/src/pages/Ativos.jsx`), a coluna da mais-valia mostra «sem
  preço», com uma dica, quando o ativo **ainda é detido** (unidades em carteira,
  ou um bem com custo por vender) e não tem preço registado, em vez de um
  «0,00 €» que parecia «sem ganho nem perda». Um ativo já vendido continua a
  mostrar o realizado, que é um valor real, e os totais por tipo continuam a
  somar o realizado. Com a D16, é o caso do Twingo, que vale o custo por falta
  de preço. Não há testes de frontend; a alteração passou no ESLint e foi
  confirmada pelo utilizador na app (o Twingo mostra «sem preço»).
- **D12c — resolvido** — `routers/patrimonio.py:94` e `:107` — dois `commit()` no mesmo
  endpoint (`criar_movimento`). Se o upsert de preço da linha 107 falhar, o
  movimento já foi gravado na linha 94: escrita parcial, sem rollback. Um
  `commit()` só, no fim, resolvia.
  **Resolvido:** `criar_movimento` faz agora um só `commit()`, no fim
  (`backend/routers/patrimonio.py:107`), depois de juntar o movimento e o
  upsert do preço (linhas 92-104): ou se gravam os dois, ou nenhum. Teste novo
  em `backend/tests/test_api_patrimonio.py`:
  `test_criar_movimento_falha_no_preco_nao_grava_o_movimento`, que provoca a
  falha com um trigger que recusa o `INSERT` em `precos_ativo` e confirma que
  ficam 0 movimentos e 0 preços.
- **D12d — resolvido** — `parser_importacao.py:9-22` — `_parse_valor` não tem forma de
  distinguir ponto decimal de separador de milhares. Isto **não** é um erro de
  configuração: com `separador_decimal="."`, `"1.234"` dar `1.234` é o
  comportamento correcto. O problema é o inverso — quando o ficheiro traz
  separador de milhares e o perfil não está configurado para o reconhecer, o
  valor é lido com um factor de 1000 errado, em silêncio. Não suporta
  parênteses de contabilidade (`(123,45)`) nem símbolos de moeda
  (`"1.234,56 €"`), que falham com `ErroParsing` — pelo menos esse caso é
  visível.
  **Resolvido (decisão do utilizador: recusar, e a importação inteira):**
  `_parse_valor` (`backend/parser_importacao.py`) recusa um texto numérico que
  não bata com o separador do perfil: o separador decimal tem de aparecer no
  máximo uma vez e no fim, e o outro só em grupos de milhares de 3 dígitos.
  `1.234,56` com o perfil em ponto, `1,234.56` com o perfil em vírgula,
  `45.60` com o perfil em vírgula e `1,5` com o perfil em ponto dão
  `ErroParsing`; `1.234` com o perfil em ponto continua a ser 1,234, porque é
  o que o perfil diz e o texto bate certo. E, por decisão do utilizador, uma
  linha com erro recusa a importação inteira (ver D29), porque um valor
  incoerente quer dizer que o perfil não serve para o ficheiro e os outros
  valores também não merecem confiança. Verificado numa cópia da BD real: o
  ActivoBank é xlsx (valores numéricos, não passam pelo texto) e o
  TradeRepublic é CSV com ponto decimal, cujos valores (`8612.0`, `-1`)
  continuam aceites; nenhuma transacção tem mais de 2 casas decimais. Os
  parênteses de contabilidade e os símbolos de moeda continuam sem suporte e
  dão erro visível. Testes na secção C de
  `backend/tests/test_parser_importacao.py`.
- **D12e — resolvido** — `parser_importacao.py:107` — `fee` é somado com o sinal tal como
  vem (`valor += _parse_valor(raw_fee, ...)`). **Confirmado pelo utilizador:** no
  extracto do Trade Republic a comissão vem NEGATIVA (por exemplo `-1`). Para
  esse banco o comportamento actual é o correcto: `-50,00 + -1,00 = -51,00`, a
  comissão aumenta a saída, como deve ser. A convenção de sinal em geral continua
  por fixar — isto só seria bug com um banco que exportasse a comissão positiva,
  caso em que a comissão reduziria a saída. Não há decisão de severidade final.
  **Relevante para os testes:**
  é uma linha, e o comportamento propaga-se a `transacoes.valor` e a tudo o que
  deriva dele — taxa de poupança, estatísticas, património.
  **Resolvido (decisão do utilizador: a comissão é sempre paga):** na
  importação, a comissão entra sempre negativa, venha com que sinal vier no
  extracto: `valor -= abs(comissão)` (`backend/parser_importacao.py`, em
  `parse_ficheiro`). Para o TradeRepublic nada muda (`-50,00` com comissão
  `-1,00` continua `-51,00`); um banco que exporte a comissão positiva passa a
  dar o mesmo resultado, e numa venda a comissão reduz o que entra. Fica nas
  «Decisões de design» do `README.md`. Testes em
  `backend/tests/test_parser_importacao.py`: o da comissão positiva foi
  invertido (`test_comissao_positiva_tambem_aumenta_a_saida`, -51,50 em vez de
  -48,50) e há um novo para a venda
  (`test_comissao_numa_entrada_reduz_o_que_entra`).
- **D12f — resolvido** — `popular_bd.py:145` — `"Certificados de Aforro"` está marcado
  `tem_unidades=False`. A confirmar, sem evidência de ser erro: certificados de
  Aforro subscrevem-se por montante e o valor acumula com juros, não se
  negociam por unidades, pelo que o ramo sem unidades parece o correcto. Fica
  anotado porque a consequência é silenciosa — um certificado passa pelo
  cálculo de custo acumulado e nunca pelo FIFO. Se algum dia se registarem
  movementos parciais, há aqui uma divergência.
  **Resolvido (decisão do utilizador: com unidades):** os Certificados de
  Aforro são subscritos em unidades (cada uma vale 1 € à subscrição e
  valoriza com os juros), e um resgate parcial é comum; sem unidades, pela
  convenção da D17, qualquer resgate seria tratado como total. Em
  `SEED_TIPOS_ATIVO` (`backend/popular_bd.py:143`) passaram a
  `tem_unidades=True`. Só afecta instalações novas: a BD real não tem este
  tipo (verificado numa cópia: só ETF, Crypto e Veículo), e o tipo continua
  editável na página Tipos de Ativo. Teste novo:
  `test_inicializar_cria_os_tipos_de_ativo_com_e_sem_unidades`
  (`backend/tests/test_api_configuracao.py`), com a lista inteira escrita à mão.
- **D12g — resolvido** — `popular_bd.py:151-173` — `popular()` não semeia
  `SEED_TIPOS_ATIVO`, ao contrário de `routers/configuracao.py:29-39`. E o
  guard da linha 158 só olha para o número de categorias: se a BD já tiver
  categorias mas nenhum tipo de ativo, `popular()` sai sem os semear.
  **Resolvido (decisão do utilizador, com a D25):** os dados iniciais ficaram
  num só sítio. `popular_bd.py` passou a chamar-se `backend/dados_iniciais.py`
  (commit `refactor` à parte) e guarda as listas e a função
  `semear_dados_iniciais`, que o `/inicializar` chama. O `popular()` e o modo
  de script (pergunta interactiva) saíram: a página de primeiro uso faz o
  mesmo, com os tipos de ativo e a marca «inicializado», e funciona no
  executável. A receita de recriar a BD no `NOTES.md` passou a usar a página de
  primeiro uso.
- **D12h — resolvido** — `routers/backups.py:104` — `filename.endswith(".db")` é
  case-sensitive: um ficheiro `BACKUP.DB` é rejeitado, e a recusa não diz
  porquê.
  **Resolvido:** a comparação passou a `file.filename.lower().endswith(".db")`
  (`backend/routers/backups.py:104`), pelo que `backup.db`, `BACKUP.DB` e
  `backup.Db` são aceites; a recusa das extensões erradas mantém-se tal e qual
  — 400 `Ficheiro inválido` (`backend/routers/backups.py:105`). Testes novos em
  `backend/tests/test_backups/test_importar.py`:
  `test_extensao_db_maiuscula_e_aceite` (linha 737),
  `test_extensao_db_com_capitalizacao_mista_e_aceite` (linha 765) e
  `test_extensao_errada_continua_a_ser_rejeitada` (linha 790).
- **D12i — resolvido** — `tray.py:19` — porta `9742` hardcoded, duplicada de
  `main.PORTA` (`main.py:207`). Alterar uma e não a outra deixa a tray a
  abrir um URL morto.
  **Resolvido:** `iniciar_tray` recebe a porta como argumento
  (`backend/tray.py:6`) e monta o URL com ela (`tray.py:19`); `main.py:268`
  passa-lhe `PORTA`, a mesma constante que o uvicorn usa. Testes novos em
  `backend/tests/test_tray.py`: `test_abrir_no_browser_usa_a_porta_recebida`
  (com um `tkinter` falso, o botão abre `http://localhost:12345` quando a porta
  é 12345) e `test_main_passa_a_porta_a_tray` (lê `main.py` com `ast`, sem o
  importar). Fica de fora a porta do frontend em dev (`frontend/vite.config.js`
  e `frontend/src/api/client.js`), que só existe no `npm run dev` e não chega ao
  executável.

### Documentação

- **D12j — resolvido** — `docs/modelo-dados.md:7` — descreve `TipoAtivo` como enum
  (`etf/crypto/veiculo/imovel/outro`); em `database.py` é uma tabela, e
  `SEED_TIPOS_ATIVO` (`popular_bd.py:139`) é quem a popula.
  **Resolvido:** `TipoAtivo` saiu da tabela de enums de `docs/modelo-dados.md`
  e ganhou secção própria (`id`, `nome`, `tem_unidades`); na secção `Ativo`, o
  campo `tipo` passou a `tipo_id` (FK → `tipos_ativo.id`), com a relação N:1.
- **D12k — resolvido** — `docs/arquitectura.md:20` — descreve uma regra de caminho da BD
  anterior à actual (não menciona `RASTREIO_DB_DIR` nem a variante
  `sys.frozen`).
  **Resolvido:** `docs/arquitectura.md:20` descreve agora a ordem de
  `_resolver_base_dir()` (`backend/database.py`): `RASTREIO_DB_DIR`, depois
  `sys.frozen`, depois `backend/`.

## ⚪ D13 — Qualidade de código

Não é bug. Dividido em sub-itens, cada um com o seu commit:

- **D13a — resolvido** — ESLint no frontend.
- **D13b — resolvido** — `ruff` no backend.
- **D13c** — `pyright` (tipos) no backend.
- **D13d** — N+1 em `calcular_patrimonio_em` / `gerar_evolucao`.
- **D13e** — índices nas colunas de data e FK, com migração da BD real e dos
  backups.

### D13a — ESLint no frontend — resolvido

Descrição original: 20 problemas do ESLint (17 erros, 3 avisos). A contagem
de 2026-10-19 era ainda 20, já sem a D14, por regra:

| Regra | Nº | Correcção |
|---|---|---|
| `no-unused-vars` | 7 | `catch {` sem variável (3), `([, v])` (1) e código morto apagado (3) |
| `react-hooks/immutability` | 5 | Função de carregamento movida para cima do `useEffect` |
| `react-hooks/set-state-in-effect` | 4 | Reset no handler (`Estatisticas`) ou estado derivado no render (`GuiaDestaque`, `FiltrosTransacoes`) |
| `react-hooks/exhaustive-deps` | 3 | Ver abaixo |
| `react-refresh/only-export-components` | 1 | Excepção comentada em `contexts/GuiaContext.jsx` |

A nota original dizia que bastava mover a função para cima do `useEffect`.
Não basta: o compilador do React passa a acusar `set-state-in-effect`, mesmo
com `useCallback`, porque não vê que o `setState` corre depois do `await`.
É um falso positivo, deixado como `eslint-disable-next-line` comentado nas
cinco páginas (`Categorias`, `Contas`, `Patrimonio`, `Regras`, `TiposAtivo`)
e em `hooks/useAtivos.js`, onde o `setLoading(true)` é preciso para o
`recarregar`.

`exhaustive-deps`:

- `FiltrosTransacoes.jsx` — o efeito chamava `onChange({ subcategoria_id: null })`
  sem categoria. Era redundante (o `<select>` da categoria já o envia) e, no
  arranque, gerava um segundo pedido de transacções igual ao primeiro. Saiu.
- `TabelaTransacoes.jsx` — `subcategorias` entrou nas dependências; a segunda
  passagem encontra tudo em cache e não faz pedidos.
- `Contas.jsx` — `carregar` passou a `useCallback([incluirInativas])`.

O CI (`test.yml`, trabalho `lint-frontend`) corre `npm run lint -- --max-warnings 0`
em cada push e pedido de integração. Os scripts de build não correm o lint.

### D13b — `ruff` no backend — resolvido

Descrição original: sem `ruff` no `venv` nem no `requirements-dev.txt`.

O `ruff` 0.17.1 (fixado no `requirements-dev.txt`) corre a partir de
`backend/` com a configuração em `backend/ruff.toml`: `E4`, `E7`, `E9`, `F` e
`I`, `line-length = 100`, `old/` excluído. Com o conjunto predefinido desta
versão havia 230 achados, sobretudo de estilo (`UP`) e 56 `B008` que são os
`Depends()` do FastAPI; com `E4,E7,E9,F` havia 26:

- 15 corrigidos à mão: imports e variáveis não usados, imports repetidos em
  `routers/perfis_importacao.py`, um import a meio de `schemas.py`, `l` como
  nome de variável, dois imports numa linha e um `lambda` atribuído num teste.
- 11 `E711`/`E712` ignorados na configuração: são filtros do SQLAlchemy
  (`Transacao.categoria_id == None`), onde o `==` gera `IS NULL`; a correcção
  sugerida, `is None`, compara em Python e partiria as queries.

A ordenação de imports (`I`) foi aplicada com `ruff check --fix`, com
`combine-as-imports` para manter os `from database import (X as XModel, ...)`
num só import. O `ruff format` foi aplicado em commit à parte, registado no
`.git-blame-ignore-revs`. O CI (`test.yml`, trabalho `testes`) corre
`ruff check` antes do pytest.

### D13c — `pyright` no backend

Sem `pyright` e quase sem anotações de tipo.

### D13d — N+1 no cálculo do património

`calcular_patrimonio_em` (`servicos/patrimonio_serv.py:151`) faz
`1 + C + 1 + 2·A` queries por ponto (contas, uma soma por conta activa, ativos,
e movimentos + preço por ativo). `gerar_evolucao` repete o cálculo por mês:
com 3 contas e 4 ativos, 13 queries por ponto e 156 para 12 meses (medido
numa BD vazia em 2026-10-19). Com os volumes desta aplicação o custo deve
ser de milissegundos: medir numa cópia da BD real antes de decidir.

### D13e — Índices

Nos modelos não há `index=True` nem `Index(...)`. `transacoes.data`,
`transacoes.conta_id`, `categoria_id`, `subcategoria_id`,
`movimentos_ativo.ativo_id`, `movimentos_ativo.data` e
`subcategorias.categoria_id` não têm índice. A excepção é `precos_ativo`,
cujo `UniqueConstraint("ativo_id", "data")` cria um índice implícito que serve
a query do preço (por confirmar numa cópia se a BD real o tem).

## 🔴 D14 — `ReferenceError` ao terminar cada importação — resolvido

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

## ⚪ D19 — Leitura de CSV com delimitador diferente de vírgula — resolvido

- `parser_importacao.py:_ler_linhas_csv` (aprox. linha 48) usa
  `csv.reader` sem `delimiter` (o valor por omissão é a vírgula). Num CSV
  delimitado por `;` (exportação típica do Excel em português), todo o conteúdo
  fica numa única coluna e todas as linhas que tenham dados são rejeitadas por
  `data inválida` — a falha é visível, não silenciosa. Esta situação está
  coberta pelo teste `test_csv_delimitado_por_ponto_e_virgula_e_lido_como_uma_coluna`
  em `backend/tests/test_parser_importacao.py`. Não decidido o curso de acção (se
  detectar automaticamente, permitir configuração do delimitador, ou documentar o
  requisito). ⚪

**Resolvido (decisão do utilizador: detectar automaticamente):**
`_detectar_delimitador` (`backend/parser_importacao.py`) escolhe, entre `,`,
`;` e tabulação, o separador que divide as linhas de dados (a partir de
`linha_inicio_dados`, até 20) no mesmo número de colunas, e no maior; se nenhum
servir, usa a vírgula, como antes. Não se usou o `csv.Sniffer`, que foi testado
e se engana num CSV com `;`, sem cabeçalho e com vírgula decimal sem aspas
(`-3,20`): escolhe a vírgula. O formato do TradeRepublic continua a ser lido
com vírgula. Se a detecção falhar num ficheiro estranho, as linhas dão erro e,
pela D29, a importação é recusada sem gravar nada. A pré-visualização usada
para criar um perfil (`analisar_ficheiro`, `routers/perfis_importacao.py`)
tinha o mesmo `csv.reader` com a vírgula fixa e passou a usar a mesma
detecção, sobre as primeiras linhas do ficheiro (o perfil ainda não diz onde
começam os dados, pelo que um preâmbulo do banco pode fazê-la voltar à
vírgula). Testes em
`backend/tests/test_parser_importacao.py`: o de caracterização foi invertido
(`test_csv_delimitado_por_ponto_e_virgula_e_detectado`), e há
`test_detectar_delimitador` (seis casos) e
`test_delimitador_detectado_so_nas_linhas_de_dados`, e em
`backend/tests/test_api_perfis_importacao.py`
`test_analisar_ficheiro_csv_delimitado_por_ponto_e_virgula_le_as_colunas`.

## 🟡 D20 — Despesa positiva sem a marca de reembolso desaparece dos totais — resolvido

`backend/routers/estatisticas.py:272-293` (`_calculate_totals`), pelo outro lado
da D4:

```python
elif t.valor < 0 and t.categoria.tipo != receita:   # 288
    meses[chave]["despesas"] += t.valor             # 289
elif t.valor > 0:                                   # 290
    meses[chave]["despesas"] += t.valor             # 291
```

Uma transação de categoria `despesa` com `valor` positivo e **sem** a marca de
reembolso não satisfaz a linha 288 (`valor < 0` falha), nem as duas que ficam
acima (não é receita nem é investimento). Antes da correcção, o último ramo
exigia a marca (`elif t.valor > 0 and t.reembolso:`), pelo que o valor
**desaparecia sem ser somado a nada** — mesma raiz da D4: nenhum ramo apanhava
o caso.

Exemplo: `-45,50` seguido de `+30,00` sem marca fechavam o mês com despesas
`-45,5` em vez de `-15,5`. A diferença na poupança é de 30,00, e a despesa
recuperada nunca chegava a aparecer em lado nenhum.

**Resolvido (decisão do utilizador: o sinal manda):** o correcto é uma despesa
positiva estar marcada como reembolso; mas, como os valores seguem o sinal, a
conta fica certa mesmo sem a marca — somar `+30,00` às despesas de `-45,50` dá
`-15,5`, que é o valor certo. Por isso o valor **não pode ser ignorado**. Mudou
`backend/routers/estatisticas.py:290`, o último ramo da cadeia: a condição
passou de `elif t.valor > 0 and t.reembolso:` para `elif t.valor > 0:`. Como é
o ramo final, qualquer valor positivo que não case com os três anteriores conta
em despesas com o sinal que tem, e a marca de reembolso deixa de ser necessária
para uma despesa entrar no cesto. Verificação nos dados reais (utilizador): existia
1 caso, de 6,15 EUR, tratado pelo próprio.

Fixo por `test_despesa_positiva_sem_marca_de_reembolso_conta_nas_despesas` em
`backend/tests/test_estatisticas_totais.py`, que fixa o comportamento
corrigido (`-45,50 + 30,00 = -15,5`, valor escrito à mão). Na altura, a D4 continuava aberta:
a receita negativa continua sem ramo que a apanhe.

## 🟡 D15 — Sobre-venda aceite em silêncio, com o encaixe reescalado — resolvido

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

**Decisão pendente (utilizador):** avisar no momento de registar a venda, ou recusar
a operação. As duas são defensáveis e divergem no que fica gravado, por isso não
se decide aqui. O teste `test_sobre_venda_escala_o_encaixe_e_nunca_avisa` fixa o
comportamento **actual**, não o desejado.

**Resolvido (decisão do utilizador: recusar):** nos ativos com unidades, a API
recusa com 422 qualquer operação que deixe uma venda acima das unidades em
carteira nessa data, com a mensagem «A venda de DD/MM/AAAA (N unidades) excede
as M unidades em carteira nessa data.»

- `primeira_sobre_venda` (`backend/servicos/patrimonio_serv.py:103`) percorre
  os movimentos pela mesma ordem do FIFO, `(data, id)`, e devolve a primeira
  venda que exceda a posição (com a mesma tolerância de `1e-9`);
- `_recusar_sobre_venda` (`backend/routers/patrimonio.py:91`) chama-a sobre a
  linha do tempo **inteira** do ativo, com a alteração já pendente na sessão, e
  desfaz tudo se houver sobre-venda. Corre ao criar uma venda (linha 134),
  porque uma venda inserida no passado pode deixar sem unidades uma venda
  posterior, e ao apagar uma compra (linha 149);
- os bens sem unidades não são verificados: o ramo deles não tem posição;
- o frontend já mostrava o `detail` ao criar; ao apagar não havia tratamento
  de erro e a recusa passaria em silêncio, por isso `MovimentosAtivo`
  (`frontend/src/pages/Ativos.jsx`) passou a mostrá-lo num `alert`, como a
  página de Importação.

Verificado numa cópia da BD real (só leitura, apagada a seguir): ainda não há
nenhuma venda registada, logo nenhuma sobre-venda nos dados. O teste de
caracterização passou a `test_sobre_venda_ja_gravada_escala_o_encaixe` e fixa o
que o núcleo do FIFO faz se uma sobre-venda já estiver gravada. Testes novos em
`backend/tests/test_api_patrimonio.py`, na secção «Sobre-venda recusada».

## ⚪ D16 — Bem sem unidades e sem preço desaparece do património — resolvido

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

**Resolvido (decisão do utilizador: o custo como valor de recurso):** sem preço
registado, um bem vale o custo de aquisição acumulado
(`backend/servicos/patrimonio_serv.py:59`); assim que tiver um preço, vale
esse preço, como antes. O custo é um facto e não uma estimativa; para um bem
que desvaloriza (uma viatura), o valor real só aparece quando se regista um
preço, e a depreciação automática por tipo de ativo fica como funcionalidade
a ponderar depois da dívida técnica. Verificado numa cópia da BD real (só
leitura, apagada a seguir): o Twingo 2020 tem 11 990,00 de compras e nenhum
preço, e passa a contar esse valor nos Bens e no total, também no gráfico
desde maio de 2024 (1 000,00) e junho de 2024 (11 990,00). Testes actualizados:
`test_evolucao_bem_sem_preco_conta_pelo_custo`,
`test_evolucao_calcula_por_mes_e_por_tipo` (cujo preço do bem passou a
14 000,00, diferente do custo, para separar os dois casos) e
`test_bem_sem_unidades_e_sem_preco_vale_o_custo`.

## ⚪ D17 — Venda parcial de um bem sem unidades tratada como venda total — resolvido

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
decisão. **Decisão pendente (utilizador):** se é erro a corrigir ou convenção a
documentar.

**Resolvido (decisão do utilizador: convenção):** um bem sem unidades vende-se
sempre por inteiro. Ficou registado nas «Decisões de design» do `README.md`,
com a alternativa para vendas parciais: registar o bem com unidades (por
exemplo 100 unidades = 100%), para que passe pelo FIFO. O código não mudou.
Verificado numa cópia da BD real: não há nenhuma venda registada, e o único bem
sem unidades é uma viatura. O cenário 13 de
`backend/tests/test_patrimonio_fifo.py` deixou de ter a etiqueta D17 e aponta
para o README.

## ⚪ D18 — Os dois pontos de entrada do cálculo escolhem preços diferentes — resolvido

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

**Resolvido (decisão do utilizador):** o valor **actual** usa o preço mais
recente, mesmo com data futura, e os pontos passados continuam históricos.

- `calcular_patrimonio_em` ganhou `precos_futuros`
  (`backend/servicos/patrimonio_serv.py`), e `gerar_evolucao` liga-o nos
  pontos a partir de hoje (`fim_mes >= hoje`; o `hoje` vem do router,
  `routers/patrimonio.py`, para os testes o poderem fixar). Assim o ponto de
  hoje do gráfico bate com os cartões, que vêm do resumo do ativo.
- O resumo do ativo não mudou: já usava o preço mais recente.
- Na página Ativos (`frontend/src/pages/Ativos.jsx`), a data do preço mostra
  «⚠» e uma dica quando é futura, porque um preço com data futura é
  normalmente um erro de introdução.

Teste novo: `test_evolucao_ponto_de_hoje_usa_o_preco_mais_recente_como_o_resumo`
em `backend/tests/test_api_patrimonio.py`, com «hoje» fixado; o teste dos
pontos passados (`test_evolucao_ignora_preco_posterior_ao_data_alvo`) continua
igual.

## ⚪ D21 — `palavra_chave` vazia ou só com espaços não é validada no servidor — resolvido

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

**Decisão pendente (utilizador):** validar no schema, no motor, ou nos dois. As três
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

## ⚪ D22 — Cópia do `.anterior` e do `.tmp` feitas no lugar — resolvido

`backend/routers/backups.py:137` — `shutil.copy2(DB_PATH, anterior_path)`
escreve o `.anterior` **no lugar** (o `copy2` abre o destino e sobrescreve o
conteúdo). Agora que o `.anterior` persiste no disco (D6), uma falha a meio da
cópia — disco cheio, por exemplo — destrói o `.anterior` bom e deixa um
ficheiro a meio, e o rollback (`backups.py:150-151`) reporia a BD a partir
dessa cópia parcial.

Pelo mesmo motivo, o `.tmp` que fique no disco se o `os.replace` da linha 141
falhar não é removido no rollback (linhas 146-155): só desaparece no pedido
seguinte, quando a limpeza inicial (linhas 116-117) o apaga.

Correcção possível (não aplicada): copiar para um ficheiro temporário e
renomear atómicamente, para que o `.anterior` só seja substituído quando a
cópia está completa —

```python
anterior_tmp = anterior_path + ".tmp"
shutil.copy2(DB_PATH, anterior_tmp)
os.replace(anterior_tmp, anterior_path)
```

— e remover também o `.tmp` no rollback.

**Resolvido:** em `importar_backup` (`backend/routers/backups.py`):

- a cópia vai para `.anterior.tmp` e só depois é renomeada para `.anterior`
  (linhas 141-142): uma falha a meio da cópia não toca no `.anterior` bom;
- o rollback só repõe a BD a partir do `.anterior` quando ele foi criado
  **neste** pedido (`anterior_pronto`, linhas 136, 143 e 158). A correcção
  proposta acima não chegava sozinha: com a cópia atómica, uma falha na cópia
  deixava a BD intacta mas o rollback repunha-a na mesma, agora a partir do
  `.anterior` de um restauro antigo, e apagava tudo o que tinha sido registado
  desde então;
- a reposição do rollback usa o mesmo padrão: copia o `.anterior` para
  `.anterior.tmp` e renomeia-o para a BD (linhas 159-160), pelo que uma falha
  a meio da reposição não deixa a BD cortada;
- o rollback remove o `.tmp` e o `.anterior.tmp` que tenham ficado
  (linhas 165-170).

Testes novos no fim de `backend/tests/test_backups/test_importar.py`, todos com
falhas simuladas por `monkeypatch`:
`test_falha_a_meio_da_copia_nao_estraga_o_anterior_nem_a_bd`,
`test_falha_na_troca_remove_o_tmp`,
`test_falha_depois_da_troca_repoe_a_bd_a_partir_do_anterior` e
`test_falha_a_meio_da_reposicao_nao_corta_a_bd`. Os dois últimos cobrem o
rollback que a D6 deixou «por cobrir».

## 🟡 D23 — Mediana por categoria do `/por-categoria` é sobre totais por (mês, subcategoria) — resolvido

A mediana de cada categoria do `/por-categoria` é calculada sobre os totais
da **linha** da query, e não sobre totais mensais. A query agrupa por
`('ano', 'mes', Transacao.categoria_id, Transacao.subcategoria_id)`
(`backend/routers/estatisticas.py:82`), e o ciclo das linhas 88-98
acrescenta `round(r.total, 2)` a `totais` **uma vez por linha** (linha 98) —
por isso uma categoria com duas subcategorias no mesmo mês contribui com dois
valores nesse mês. A mediana (linha 110, `median(cat["totais"])`) é calculada
sobre essa lista de totais por (mês, subcategoria).

Exemplo do teste (`test_por_categoria_media_com_zeros_e_mediana_sem_preenchimento`
em `backend/tests/test_api_estatisticas.py`), com a categoria Casa e as
subcategorias Renda e (sem subcategoria) a dividirem março:

- totais por (mês, subcategoria): `[-100, -30, -40, -30]` →
  `median([-100, -40, -30, -30])` = `(-40 + -30) / 2` = **-35.0**;
- se fosse calculada por mês, os totais mensais seriam
  `[-130, -40, -30]` → mediana **-40.0**.

A média não é afectada: soma por (mês, subcategoria) ou por mês dá o mesmo,
e o denominador é `meses_distintos` (linha 111).

**Decisão pendente (utilizador):** qual é a mediana pretendida — por mês, ou por
(mês, subcategoria)?

**Resolvido (decisão do utilizador: por mês, com os meses vazios a zero):** a
coluna chama-se «Mediana mensal» e aparece ao lado da «Média mensal»
(`frontend/src/pages/Estatisticas.jsx:287-288`), por isso as duas passam a
descrever os mesmos meses. Em `por_categoria` (`backend/routers/estatisticas.py`):

- a categoria soma as linhas de cada mês antes de calcular a mediana
  (`por_mes`, linha 108);
- `_mediana_mensal` (linha 57) acrescenta um zero por cada mês do período sem
  movimentos (`meses_distintos`), tal como a média já fazia pelo denominador;
- o mesmo vale para as subcategorias.

Isto também resolve o caso das categorias esporádicas: Férias com -1200,00 em
2 meses de 12 tinha «mediana mensal» -1200,00; passa a 0,00, ao lado da média
de -200,00. Pela convenção da D5, os meses só com transferências também
contam como zero. Os dois testes do `/por-categoria` em
`backend/tests/test_api_estatisticas.py` passaram a afirmar as medianas novas
(Renda -70 → -20, Sem subcategoria -30 → -15; a Casa fica em -35 por
coincidência), e o teste novo
`test_por_categoria_mediana_por_mes_e_nao_por_subcategoria` usa um cenário em
que as quatro maneiras de calcular dão valores diferentes.

## ⚪ D24 — Nome duplicado de categoria dá 500, ao contrário de contas (409) e regras (400) — resolvido

`POST /api/categorias/` (`backend/routers/categorias.py:33-35`) e
`PUT /api/categorias/{id}` (`backend/routers/categorias.py:63-70`) não têm
pré-checagem de nome duplicado: escrevem e fazem `commit()` (linhas 35 e 70), e
`categorias.nome` é `unique=True` (`database.py:155`). O `IntegrityError:
UNIQUE constraint failed: categorias.nome` sobe sem ser tratado e em produção é
um **500**.

O mesmo defeito existe no `PUT /api/tipos-ativo/{tipo_id}`
(`backend/routers/tipos_ativo.py:25-32`): ao contrário do `POST`
(`routers/tipos_ativo.py:14-16`, que pré-checa e responde **409**), o `PUT`
escreve o `nome` (linha 28) e faz `commit()` (linha 30) sem pré-checagem, e
`tipos_ativo.nome` é `unique=True` (`database.py:125`). Renomear para um nome
existente rebenta com `IntegrityError: UNIQUE constraint failed: tipos_ativo.nome`
— em produção, um **500**.

Os mesmos casos noutros routers devolvem um 4xx explícito:

- `routers/contas.py:19-21` — `criar_conta` pré-checa o nome e responde **409**
  "Já existe uma conta com este nome.";
- `routers/regras.py:35-37` — `criar_regra` pré-checa a palavra-chave e responde
  **400** "Já existe uma regra com esta palavra-chave".

Possível defeito de consistência: a mesma condição de negócio (nome/palavra-chave
repetida) responde 409 numa rota, 400 noutra e 500 nas categorias. **Decisão
pendente (utilizador):** alinhar categorias por pré-checagem (e com que código), ou
deixar a excepção subir.

**Resolvido:** decisão do utilizador — pré-checagem e **409** nos três sítios, com
mensagem em PT-PT no estilo de `contas.py` e do POST de tipos de ativo. As
linhas abaixo são as de **antes** da correcção (a descrição acima ficou como
está); as que se seguem foram lidas no código depois dela:

- `backend/routers/categorias.py:33-35` — `criar_categoria` pré-checa
  `Categoria.nome` e responde 409 `"Já existe uma categoria com este nome."`
  (`:35`);
- `backend/routers/categorias.py:71-73` — `renomear_categoria` pré-checa contra
  as **outras** categorias (`Categoria.id != categoria_id`, `:71`) e responde o
  mesmo 409 (`:73`): re-submeter o próprio nome não é duplicado e continua 200;
- `backend/routers/tipos_ativo.py:28-30` — `renomear_tipo_ativo` pré-checa
  contra os **outros** tipos (`TipoAtivo.id != tipo_id`, `:28`) e responde 409
  `"Já existe um tipo de ativo com este nome."` (`:30`), a mesma frase do POST
  (`backend/routers/tipos_ativo.py:16`).

A diferença de código com `regras.py` fica como estava: `routers/regras.py:37`
continua a responder **400** pela palavra-chave — não fez parte desta decisão.
Os testes que fixavam o 500 passaram a afirmar o 409, o corpo (`detail`) e o
estado final da BD (`session.expire_all()`, nada alterado), e cada router ganhou
um teste do PUT com o próprio nome a 200:
`test_criar_categoria_e_nome_duplicado_da_409`,
`test_renomear_categoria_duplicado_da_409_e_404` e
`test_renomear_categoria_mantendo_o_proprio_nome_e_200`
(`backend/tests/test_api_categorias.py`);
`test_renomear_tipo_ativo_para_nome_duplicado_da_409` e
`test_renomear_tipo_ativo_mantendo_o_proprio_nome_e_200`
(`backend/tests/test_api_tipos_ativo.py`).

## ⚪ D25 — `/api/configuracao/inicializar` semeia categorias duplicadas e dá 500 — resolvido

`POST /api/configuracao/inicializar` (`backend/routers/configuracao.py:15-48`)
só guarda contra a re-semente quando existe uma linha `Configuracao` já marcada
como inicializada (`configuracao.py:21-23`, `if config and config.inicializado`).
Se a tabela `categorias` já tiver linhas mas não existir linha `Configuracao`, o
guard não dispara, o ciclo das linhas 29-35 volta a inserir os mesmos nomes e o
`commit()` da linha 46 falha com `IntegrityError: UNIQUE constraint failed:
categorias.nome` (`categorias.nome` é `unique=True`, `database.py:155`) — em
produção, um **500**.

É a mesma classe de robustez da D12g: `popular()`
(`backend/popular_bd.py:151-173`) tem um guard análogo, mas também só olha para
o número de categorias (`popular_bd.py:158`) e não para `Configuracao`. As duas
vias divergem no que consideram "base já semeada": `inicializar` olha para
`Configuracao`, `popular` olha para `categorias`.

**Decisão pendente (utilizador):** o guard de `inicializar` deve olhar também para as
categorias existentes, ou semear de forma idempotente?

Fixo por `test_inicializar_com_categorias_existentes_sem_config_integrity` em
`backend/tests/test_api_configuracao.py`, que fixa o comportamento **actual**:
com uma categoria "Casa" na BD e sem linha `Configuracao`, o pedido rebenta com
`IntegrityError` e nada fica inicializado.

**Resolvido (decisão do utilizador: semear de forma idempotente, com a
D12g):** `semear_dados_iniciais` (`backend/dados_iniciais.py`) cria, pelo
nome, só as categorias, subcategorias e tipos de ativo que faltam; o que já
existe não é tocado, e o `/inicializar` deixa de poder dar 500 por nome
duplicado. Isto cobre os dois caminhos que levavam ao erro: uma BD criada pelo
antigo `popular_bd.py` (categorias sem configuração) e o restauro de um backup
nesse estado. O teste de caracterização foi invertido
(`test_inicializar_com_dados_existentes_cria_so_o_que_falta`, em
`backend/tests/test_api_configuracao.py`), com uma categoria e um tipo da lista
já existentes e uma subcategoria e um tipo fora dela.

## ⚪ D26 — Ativo com unidades e sem preço desaparece do património — resolvido

O mesmo problema da D16, no ramo com unidades. Em `_resumo_valor_ativo`
(`backend/servicos/patrimonio_serv.py:101`), um ativo com unidades em carteira
e sem nenhum preço registado tem `valor = 0.0`:

```python
valor = round(quantidade * float(preco.preco), 2) if (preco and quantidade > 0) else 0.0
```

O custo aparece no `custo_total`, mas o ativo contribui 0 para os
`investimentos` e para o `total` do património. A D16 só tratou dos bens sem
unidades (que passaram a valer o custo).

Na prática é raro: uma compra registada pela API com `preco_unitario` cria logo
um preço para essa data (`criar_movimento`, `routers/patrimonio.py`). Só
acontece com compras sem preço unitário, ou se o preço for apagado à mão.

Fixo por `test_sem_preco_degrada_o_latente_para_nulo` em
`backend/tests/test_patrimonio_fifo.py`, que fixa o comportamento **actual**
(valor 0,0 com 100,00 de custo). **Decisão pendente (utilizador):** valer o
custo, como os bens desde a D16, ou outra regra.

**Resolvido (decisão do utilizador: o custo, como na D16):** sem preço
registado, um ativo com unidades em carteira vale o custo FIFO dessas unidades
(`custo_base`, `backend/servicos/patrimonio_serv.py`, ramo com unidades de
`_resumo_valor_ativo`); com preço vale `quantidade x preço`, como antes, e sem
unidades vale 0. A página Ativos mostra «sem preço» na mais-valia (D12b). Vale
também para a evolução: um ponto anterior ao primeiro preço conta pelo custo.
Testes actualizados: `test_sem_preco_vale_o_custo_e_o_latente_e_nulo`
(`backend/tests/test_patrimonio_fifo.py`) e
`test_evolucao_ignora_preco_posterior_ao_data_alvo` (100,00 em vez de 0,00,
`backend/tests/test_api_patrimonio.py`).

## 🟡 D27 — Um preço registado não se pode apagar — resolvido

Encontrado pelo utilizador ao testar a D18 na app. A API só tinha
`POST /api/patrimonio/precos`, que grava ou actualiza o preço de um dia: não
havia listagem, nem `DELETE`, nem histórico de preços na página Ativos. Um preço
com o valor errado só se corrigia voltando a registar o mesmo dia; um preço com
a **data** errada não se corrigia de todo. Com a D18 o caso da data futura
ficava pior: registar o preço outra vez na data certa criava outra linha, e a
futura continuava a ser «a mais recente», usada no resumo e no ponto de hoje,
até essa data passar.

**Resolvido (decisão do utilizador: listar e apagar, e recusar datas
futuras):** em `backend/routers/patrimonio.py`:

- `registar_preco` recusa com 422 «A data do preço não pode ser futura.» uma
  data depois de hoje (um preço é uma observação); a data de hoje é aceite;
- `GET /ativos/{id}/precos` (`listar_precos`) lista os preços do ativo, do mais
  recente para o mais antigo;
- `DELETE /precos/{id}` (`eliminar_preco`) apaga um preço.

Na página Ativos (`frontend/src/pages/Ativos.jsx`), a linha expandida do ativo
mostra os preços com um botão para apagar (`PrecosAtivo`, no mesmo padrão de
`MovimentosAtivo`), e o campo de data do registo de preço não deixa escolher
uma data futura (`max`). O «⚠» da D18 fica para preços futuros já gravados.
Confirmado pelo utilizador na app, sobre uma cópia da BD: o «⚠», a lista de
preços, o apagar de um preço com data futura e a recusa de uma data futura no
registo.

Fica de fora: uma compra com `preco_unitario` e data futura continua a criar um
preço futuro pela via de `criar_movimento`; a data dos movimentos não é
validada. Testes novos em `backend/tests/test_api_patrimonio.py`:
`test_registar_preco_com_data_futura_da_422`,
`test_listar_precos_do_mais_recente_para_o_mais_antigo` e
`test_eliminar_preco_apaga_so_esse_preco`.

## ⚪ D28 — A pesquisa por descrição só ignora maiúsculas em letras sem acento — resolvido

`backend/routers/transacoes.py:46` filtra a listagem de transacções com
`Transacao.descricao.ilike(f"%{descricao}%")`. O `LIKE` do SQLite só ignora
maiúsculas em letras ASCII, por isso:

- «FARMÁCIA» não encontra «farmácia» (o «Á» e o «á» não são iguais);
- «farmacia», sem acento, não encontra «Farmácia»;
- `%` e `_` no texto pesquisado funcionam como curingas.

É a mesma limitação que o backfill das regras tinha até à D8, mas numa
pesquisa e não no motor de regras. Fixo por
`test_listar_filtra_por_descricao_ascii` em
`backend/tests/test_api_transacoes.py`, que fixa o comportamento **actual**.

**Decisão pendente (utilizador):** igualar à comparação das regras
(`casa_palavra`: ignora maiúsculas também nas letras acentuadas, texto
literal), ou ir mais longe e ignorar também os acentos, para «farmacia»
encontrar «Farmácia». Qualquer das duas tira o filtro do SQL, o que tem de ser
feito antes da paginação (o `total` tem de contar só as que casam).

**Resolvido (decisão do utilizador: ignorar também os acentos):** a pesquisa
compara a descrição e o texto procurado depois de `_para_pesquisa`
(`backend/routers/transacoes.py`), que tira os acentos (decomposição NFKD) e as
maiúsculas (`casefold`): «farmacia», «FARMÁCIA» e «Farmácia» encontram-se umas
às outras, e `%` e `_` são texto. O filtro saiu do SQL e corre em Python sobre
as transacções que passam os outros filtros, antes da paginação, pelo que o
`total` e as páginas contam só as que casam. As regras de categorização não
mudaram: continuam a distinguir acentos (D8). Testes em
`backend/tests/test_api_transacoes.py`:
`test_listar_filtra_por_descricao_sem_acentos_nem_maiusculas` (invertido) e
`test_listar_por_descricao_pagina_so_as_que_casam`.

## 🟡 D29 — A importação ignorava as linhas com erro sem o dizer — resolvido

Encontrado ao corrigir a D12d. `importar_extrato`
(`backend/routers/importacao.py`) só recusava o ficheiro quando **nenhuma**
linha era válida; com pelo menos uma válida, gravava essas e deixava as linhas
com erro de fora, e a resposta (`inseridas`, `duplicadas`) não as mencionava.
Só a pré-visualização as mostrava.

**Resolvido (decisão do utilizador: qualquer erro recusa tudo):** se o parser
devolver algum erro, a importação responde 400 e não grava nada, com a
mensagem «Nada foi importado: o ficheiro tem N linha(s) com erro (a primeira é
a linha L: ...). Corrige o ficheiro ou o perfil; a pré-visualização mostra
todas.» O frontend já mostra o `detail` num `alert`. Consequência aceite: um
extracto com uma linha de totais no fim tem de ser limpo antes de importar.
Fica nas «Decisões de design» do `README.md`. Testes:
`test_importar_sem_transacoes_validas_da_400` (mensagem nova) e
`test_importar_com_uma_linha_com_erro_nao_importa_nenhuma`, em
`backend/tests/test_api_importacao.py`.

## ⚪ D30 — `.CSV` em maiúsculas tratado como Excel na criação de perfis — resolvido

Encontrado ao corrigir a D19. `analisar_ficheiro`
(`backend/routers/perfis_importacao.py:32`), a pré-visualização usada para
criar um perfil, decidia o tipo com `nome.endswith(".csv")`, que distingue
maiúsculas: um `EXTRACTO.CSV` era aberto com o `openpyxl` e falhava. É a mesma
classe da D12h (extensão `.DB` nos backups).

**Resolvido:** a comparação passou a `nome.lower().endswith(".csv")`. Teste
novo: `test_analisar_ficheiro_csv_com_extensao_em_maiusculas`, em
`backend/tests/test_api_perfis_importacao.py`. A importação em si não é
afectada: usa o `tipo_ficheiro` do perfil, e não o nome do ficheiro.

---

## Regra a seguir

Ao corrigir qualquer item, no mesmo commit, corrige o código, ajusta ou
acrescenta o teste que o fixa, e marca o item como **Resolvido**. Assim a
mudança fica explícita no histórico em vez de ser um efeito colateral.
