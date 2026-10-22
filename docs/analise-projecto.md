# Rastreio-DB — Análise do projecto

21 de Outubro de 2026

## Contexto e método

Levantamento imparcial do código, da lógica de negócio, da documentação e da organização do Rastreio-DB, feito área a área e sem corrigir nada. As correcções vêm no fim, uma a uma.

- **Fontes:** só o estado actual dos ficheiros. Sem histórico do git, sem PRs, sem `NOTES.md`.
- **Segurança:** a BD real nunca foi aberta. Todas as reproduções correram em cópias em `/tmp/rastreio-analise/`, com `RASTREIO_DB_DIR` e `HOME` apontados para `/tmp`.
- **Cada achado** tem `ficheiro:linha`, uma reprodução quando é possível, o estado (confirmado ou suspeito), a gravidade e as opções de correcção.
- **Gravidade:** crítica (perde ou corrompe dados, ou dá números errados sem aviso), alta, média ou baixa.
- **Decisões de design do README:** quando as questiono, marco-as como «decisão a rever» e não como defeito.
- **Correcções:** cada achado resolvido ganha uma linha «Resolvido» com o commit, e o resumo no fim diz quais estão feitos.

**Plano aprovado (12 áreas):**

0. Ponto de partida
1. Modelo de dados e persistência
2. Transações, categorias, contas e regras
3. Importação
4. Estatísticas e liquidez
5. Ativos, FIFO e património
6. Backups e restauro
7. Segurança e robustez do servidor local
8. Frontend, incluindo se as estatísticas dão uma visão correcta
9. Testes
10. Build, CI, empacotamento e dependências
11. Documentação, AGENTS.md e organização

**Referências a análises anteriores, ignoradas:**

- etiquetas «B4» em `backend/main.py:37`, `:107` e `backend/database.py:56`;
- «B1» em `backend/tests/test_api_contas.py:231`;
- «B1 a B30» e «relatório de cobertura» em `backend/tests/test_api_patrimonio.py:5`, `:13-14`;
- «A14» e «relatório de cobertura» em `backend/tests/test_api_perfis_importacao.py:5`, `:18`;
- «bug B3» em `backend/tests/test_api_regras_massa.py:20`, `:96`.

## Área 0 — Ponto de partida

O projecto estava verde à partida: os 359 testes passam e o lint passa sem avisos.

| Verificação | Resultado |
| --- | --- |
| `./backend/test.sh` | 359 passed in 5.67s |
| `ruff check` | All checks passed! |
| `ruff format --check` | 46 files already formatted |
| `pyright` | 0 errors, 0 warnings |
| `npm run lint -- --max-warnings 0` | sem avisos |
| BD real, md5 | `8e6d8ac8cc48f83e2ab07576f078278f` |
| BD real, stat | 159744 bytes, modificada a 2026-10-19 21:20:40 |

Na cópia da BD real, `integrity_check` dá `ok`, `foreign_key_check` não dá violações e o modo de journal é `delete`. A sandbox fica em `/tmp/rastreio-analise/`: o código em `repo/`, a cópia limpa da BD em `bd/` e uma cópia por sonda (`p1/`, `p1b/`, `p2/`, `p2c/`).

## Área 1 — Modelo de dados e persistência

Três achados confirmados: um de gravidade alta (não há controlo da versão do schema) e dois baixos.

### 1.1 Uma BD de uma versão anterior arranca sem erro e depois falha nalgumas páginas

A aplicação não guarda que versão de schema tem a BD. `criar_tabelas()` só cria as tabelas que faltam e nunca acrescenta colunas. Os scripts `migrar_*.py` não vão no executável. Quem actualiza a aplicação e mantém a pasta `dados/` antiga, ou restaura um backup antigo, vê a aplicação abrir normalmente e depois receber erros 500.

- **Resolvido:** em `cf92195`. A BD guarda a versão do schema (`PRAGMA user_version`) e as migrações numeradas de `MIGRACOES` correm no arranque e no restauro; se ainda faltar alguma coluna, o arranque recusa e diz o que falta. As 8 migrações anteriores a Julho não foram reescritas: uma BD dessa altura é recusada com a mensagem, em vez de dar 500 (ver 7.4).
- **Gravidade:** alta. **Categoria:** robustez / estrutura. **Estado:** confirmado.
- **Onde:** `backend/database.py:384-386` (só `create_all` e a reparação de `ativos_old`). Não há `user_version` em parte nenhuma. O padrão manual via-se nos scripts de `backend/old/`, apagados no 11.1 (estão no histórico do git).
- **Prova:** `/tmp/rastreio-analise/area1b.py` corre numa cópia sem a coluna `coluna_fee`. O arranque (`_preflight`) conclui sem erro; `/api/perfis-importacao/` dá 500 e `/api/transacoes/` dá 200.
- **Opções:**
  - (a) `PRAGMA user_version` com migrações aplicadas no arranque. É o mais completo; os scripts futuros passam a seguir esse formato.
  - (b) Verificar as colunas no arranque e recusar com uma mensagem clara. É simples, mas o utilizador fica bloqueado até alguém migrar.
  - (c) Alembic. É a solução padrão, mas traz uma dependência nova.
  - Qualquer delas interessa também ao restauro de backups (Área 6).

### 1.2 Apagar uma conta tira-a, sem aviso, aos perfis de importação

Uma conta sem transações apaga-se mesmo com perfis de importação associados. O ORM põe o `conta_id` desses perfis a `NULL` sem dizer nada, e a importação seguinte com esse perfil entra sem conta. O comentário em `database.py:92-94` diz que apagar um pai com filhos é recusado, o que não é verdade.

- **Resolvido:** com a opção (a). Em `bc2f774`, a importação passou a recusar, com uma mensagem clara, um perfil que perdeu a conta, e o formulário deixou de criar ou editar um perfil sem conta. Depois, uma conta sem transações e com perfis associados deixou de se poder apagar (409, mostrado na página Contas); com transações, continua a ser desactivada e o perfil fica com ela. O comentário de `database.py` foi corrigido.
- **Gravidade:** baixa. **Categoria:** correcção / documentação. **Estado:** confirmado.
- **Onde:** `backend/routers/contas.py:46-59` e `backend/database.py:160-162`.
- **Prova:** `/tmp/rastreio-analise/area1.py` → `DELETE conta com perfil -> 200 eliminada`; depois, o perfil tem `conta_id = None`.
- **Opções:**
  - (a) Recusar com 409 enquanto houver perfis associados, como nos tipos de ativo.
  - (b) Manter o comportamento e avisar na resposta.
  - (c) Só corrigir o comentário. O mesmo mecanismo serve, de propósito, a subcategoria apagada.

### 1.3 Nomes repetidos ou vazios em subcategorias e categorias

Podem criar-se duas subcategorias com o mesmo nome na mesma categoria, e uma categoria com um nome feito só de espaços. Isto aparece como opções repetidas nos selectores e como estatísticas divididas em linhas com o mesmo nome.

- **Gravidade:** baixa. **Categoria:** robustez. **Estado:** confirmado.
- **Onde:** `backend/routers/categorias.py:47-62`, `backend/schemas.py:10-12,29-31` e `backend/database.py:179-187` (sem restrição de unicidade).
- **Prova:** `sub duplicada 'Salário' -> 200`; `categoria nome só espaços -> 200`.
- **Opções:**
  - (a) Validar no router e no schema (`strip`, tamanho mínimo 1, 409 se duplicado). Não precisa de migração.
  - (b) `UniqueConstraint(categoria_id, nome)`. Obriga a recriar a tabela (ver 1.1).
- **Resolvido:** com a opção (a), só no router. Os nomes perdem os espaços à volta, um nome vazio dá 400, e um nome repetido dá 409: nas categorias, entre todas; nas subcategorias, dentro da mesma categoria. A comparação ignora maiúsculas e acentos (decisão no README). A página Categorias passou a mostrar os erros das subcategorias. Numa cópia da BD, não havia nomes vazios nem repetidos por esta regra. As categorias predefinidas continuam a comparar o nome exacto ao semear.

### Suspeitos, a confirmar em áreas seguintes

- As colunas de enumeração não têm `CHECK`. Um backup com valores inesperados pode partir as listagens (Área 6).
- `ativos.moeda` é guardado mas nunca usado: o frontend envia sempre «EUR» (Área 5).
- Nas categorias predefinidas, «Património» é do tipo `despesa` e «Casa › Prestação» trata património. A mesma saída pode contar duas vezes (Áreas 4 e 5).
- Limpar o símbolo de um ativo não funciona: o frontend envia `null` e o backend lê-o como «não alterar». Já está confirmado e entra na Área 5.

### O que está bem

- **Chaves estrangeiras:** estão activas em todas as ligações. Na cópia, `integrity_check` dá ok e não há violações.
- **Dados reais coerentes** (verificados na cópia):
  - nenhuma transação tem uma subcategoria de outra categoria, e nenhuma regra está incoerente;
  - nenhum valor tem mais de 2 casas decimais;
  - não há subcategorias duplicadas nem booleanos a `NULL`.
- **Schema da BD real:** difere do schema de raiz só na ordem das colunas, em defaults e na nulidade de 2 booleanos. Hoje isso não tem efeito.
- **Reparação de `ativos_old`:** é idempotente, corre numa transação e verifica a cópia. A BD real já está reparada.
- **Dinheiro:** é guardado em `Float`, mas todas as leituras arredondam com `exato` e `arredondar` (via `Decimal`). NaN e infinito são recusados no schema e no parser. Os restos binários ficam abaixo do cêntimo.
- **Dados iniciais:** são idempotentes por nome, e `/inicializar` recusa uma segunda inicialização.
- **Sessões:** há uma sessão por pedido, que é sempre fechada. A importação faz um único commit, com rollback em caso de erro.

## Área 2 — Transações, categorias, contas e regras

O achado principal: na tabela de transações não se consegue mudar a categoria de uma transação que já tem subcategoria, e a falha é silenciosa. Os restantes achados são de documentação e de contagens.

### 2.1 Não se consegue mudar a categoria de uma transação que já tem subcategoria

O frontend envia dois pedidos: primeiro a categoria nova, depois a subcategoria a vazio. O backend valida a subcategoria antiga contra a categoria nova e recusa com 400, e o segundo pedido nunca chega a sair. A caixa volta ao valor antigo sem mensagem nenhuma. Escolher «—» falha da mesma forma.

- **Resolvido:** em `b78dcb8`, com a opção (a). A tabela envia `{categoria_id, subcategoria_id: null}` num só pedido, e um `PUT` que falha mostra o `detail` do erro. O backend fica igual, e um teste novo fixa o pedido combinado. Verificado com o lint; não testado no browser.
- **Gravidade:** média. **Categoria:** correcção (incoerência entre o frontend e o backend). **Estado:** backend confirmado; frontend confirmado por leitura; não testado no browser.
- **Onde:**
  - `frontend/src/components/TabelaTransacoes.jsx:54-57` (dois pedidos, sem `catch`);
  - `frontend/src/pages/Transacoes.jsx:100-108`;
  - `backend/routers/transacoes.py:104-117`;
  - o teste `backend/tests/test_api_transacoes.py:598-628` fixa o 400 como intencional.
- **Prova:** `/tmp/rastreio-analise/area2.py` → `PUT categoria_id=outra -> 400 'A subcategoria não pertence à categoria selecionada.'`; com `null` dá o mesmo 400.
- **Opções:**
  - (a) O frontend envia `{categoria_id, subcategoria_id: null}` num só pedido.
  - (b) O backend limpa a subcategoria quando a categoria muda. Muda o contrato fixado pelo teste.
  - Em ambos os casos: mostrar o erro quando um `PUT` falha.

### 2.2 Uma regra «nunca atribuir categoria» ganha sempre, ao contrário do que diz o README

O README diz que ganha a palavra-chave mais longa. O código, no entanto, verifica primeiro todas as exclusões, qualquer que seja o comprimento. Uma exclusão curta («MB») bloqueia uma regra específica («MB WAY SALARIO») sem explicação.

- **Gravidade:** baixa. **Categoria:** documentação / lógica de negócio. É uma decisão a esclarecer. **Estado:** confirmado.
- **Onde:** `backend/importador_transacoes.py:12-17`, `backend/routers/regras.py:64-68`, `:121-132` e o 9.º ponto das «Decisões de design» no `README.md`.
- **Prova:** `/tmp/rastreio-analise/area2b.py` → a ordem é `['MB WAY SALARIO', 'MB']` e o resultado é `None None`.
- **Opções:**
  - (a) Documentar que as exclusões ganham sempre.
  - (b) Pôr as exclusões na ordem por comprimento. Muda os resultados de quem já tem exclusões curtas.
- **Resolvido:** com a opção (a). O código fica igual, e o README diz que uma exclusão ganha sempre, seja qual for o comprimento.

### 2.3 A página Conceitos descreve funcionalidades de regras que não existem

O texto diz que se pode editar uma regra e escolher se se aplica retroactivamente. Não existe edição de regras, e criar uma regra aplica-a sempre às transações que lhe correspondem.

- **Gravidade:** baixa. **Categoria:** documentação. **Estado:** confirmado por leitura.
- **Onde:** `frontend/src/pages/Sobre.jsx:62-67`, `backend/routers/regras.py:37-95` e `frontend/src/api/regras.js`.
- **Opções:**
  - (a) Corrigir o texto.
  - (b) Implementar a edição e a escolha retroactiva. É uma funcionalidade nova.
- **Resolvido:** com a opção (a). O texto da página Conceitos descreve o que a aplicação faz: uma regra nova aplica-se logo às transações por categorizar ou da mesma categoria sem subcategoria, os conflitos resolvem-se no «Aplicar regras às transações», e uma regra não se edita. O histórico do git confirma que a edição de regras nunca existiu (o router nunca teve `PUT`). A (b) fica como funcionalidade para depois.

### 2.4 «Aplicar regras» conta como actualizadas transações em que nada muda

Uma transação com a categoria certa e sem subcategoria, mais uma regra da mesma categoria sem subcategoria: a transação aparece como «será actualizada» e entra na contagem, mas fica igual. Volta a aparecer sempre que se abre o modal.

- **Gravidade:** baixa. **Categoria:** correcção (contagens enganadoras). **Estado:** confirmado num caso construído. Nos dados reais a pré-visualização está vazia.
- **Onde:** `backend/routers/regras.py:136-137`, `:78-92` e `:228-230`.
- **Prova:** `/tmp/rastreio-analise/area2d.py` → `transacoes_atualizadas = 1` e `aplicadas: 1`. A transação fica `cat 1 sub None`, como estava antes.
- **Opções:**
  - (a) Excluir os casos sem efeito da pré-visualização e das contagens.
  - (b) Documentar.
- **Resolvido:** com a opção (a). Uma transação que já tem a categoria da regra, quando a regra não traz subcategoria, deixa de aparecer na pré-visualização e de contar ao criar a regra; e a aplicação em massa não conta como aplicado um item igual ao que já está. A regra que não muda nada continua a decidir sozinha: a seguinte não é avaliada. O teste que fixava a contagem antiga passou a fixar a nova.

### 2.5 Uma regra aceita uma subcategoria de outra categoria

O backend só confirma que a subcategoria existe, e não que pertence à categoria. Pela interface isto não acontece, só pela API. Além disso, «Continente» e «CONTINENTE» são aceites como regras distintas, e a mais recente nunca é usada.

- **Gravidade:** baixa. **Categoria:** robustez. **Estado:** confirmado.
- **Onde:** `backend/routers/regras.py:39-45`.
- **Prova:** `regra com sub de outra categoria -> 200`; `mesma palavra noutra caixa -> 200`.
- **Opções:**
  - (a) Validar que a subcategoria pertence à categoria e comparar duplicados sem distinguir maiúsculas.
  - (b) Deixar como está.
- **Resolvido:** com a opção (a). Ao criar uma regra, a subcategoria tem de ser da categoria da regra (400 se não for, também numa regra sem categoria), e uma palavra-chave igual a outra sem distinguir maiúsculas é recusada, como já é a comparação com as descrições. Mutações: duplicado exacto e sem verificar a categoria da subcategoria, ambos mortos.

### 2.6 Não há forma de apagar nem de criar transações à mão

O router de transações só tem `GET` e `PUT`. Uma importação para a conta errada só se desfaz restaurando um backup, e uma despesa em dinheiro vivo não se consegue registar. O README não refere isto nas «Limitações».

- **Gravidade:** a definir. **Categoria:** lógica de negócio. **Estado:** confirmado por leitura (`backend/routers/transacoes.py`).
- **Em aberto:** decidir se é um achado ou uma limitação a documentar.
- **Opções:**
  - (a) Documentar nas «Limitações».
  - (b) Acrescentar a remoção, que tem de lidar com os movimentos de ativo ligados à transação.
  - (c) Acrescentar a criação manual.
- **Resolvido:** com a opção (a). É uma limitação aceite, e está nas «Limitações» do README.

### O que está bem

- **Apagar categorias e subcategorias:** conforme o README. Uma categoria com transações é recusada; uma subcategoria apagada deixa as transações na categoria e as regras sem subcategoria.
- **Apagar conta:** uma conta com transações é desactivada, não apagada.
- **`PUT` de transações:** valida a coerência entre a categoria e a subcategoria antes de qualquer escrita.
- **Precedência entre regras com categoria:** a mais longa primeiro e, em empate, a mais antiga. A primeira que casa decide sozinha.
- **Aplicação em massa:** devolve em separado os ids inexistentes e os pares incoerentes.
- **Pesquisa por descrição:** ignora acentos e maiúsculas e é feita antes de paginar, por isso o total está certo.
- **Contador «por categorizar»:** é coerente com o filtro.
- **BD real** no fim da área: md5 `8e6d8ac8cc48f83e2ab07576f078278f`, 159744 bytes, modificada a 2026-10-19 21:20:40.

## Área 3 — Importação

Nesta área há dois achados que podem estragar números sem aviso: um débito que vem negativo no extracto entra como receita, e uma transação igual a outra pode ser descartada como duplicada. O terceiro achado é que só se aceita CSV em UTF-8.

### 3.1 No modo de duas colunas, um débito que vem negativo no extracto entra como receita

O valor é calculado como `crédito − débito`. Se o banco já escreve o débito com sinal menos («-12,50»), a compra entra como +12,50. A pré-visualização mostra-o assim, mas sem aviso, e só mostra as primeiras 10 linhas. A comissão, ao contrário, é tratada com `abs()`.

- **Resolvido:** em `5f639a2`. O valor passa a ser |crédito| − |débito|.
- **Gravidade:** alta. Para um banco que exporta neste formato é crítica: todas as despesas passam a receitas. **Categoria:** correcção. **Estado:** confirmado.
- **Onde:** `backend/parser_importacao.py:131-147` (compare-se com `:149-154`, onde a comissão usa `abs`).
- **Prova:** `/tmp/rastreio-analise/area3.py`, caso 1 → `('COMPRA SUPERMERCADO', 12.5)`, sem erros.
- **Opções:**
  - (a) Usar `abs()` nas duas colunas, como na comissão: o débito subtrai sempre e o crédito soma sempre. É uma regra de negócio nova, a decidir.
  - (b) Recusar a linha quando o débito vem negativo, e pedir que se corrija o perfil.
  - (c) Uma opção no perfil, «débito vem com sinal».

### 3.2 Uma transação igual a outra já importada é descartada como duplicada

Uma linha é considerada duplicada se já existe na conta outra com a mesma data, descrição, valor e saldo. A comparação é feita contra um conjunto e não conta quantas vezes cada linha aparece. Exemplo: um extracto exportado ao meio-dia traz um café do dia 3, o extracto seguinte traz os dois cafés desse dia, e o segundo café é descartado. Só acontece quando o perfil não tem coluna de saldo, porque o saldo distingue as duas linhas.

- **Resolvido:** em `58573d4`. Contam-se as cópias de cada linha: cada uma na BD absorve uma linha igual do extracto, e as restantes entram.
- **Gravidade:** média (perde-se uma transação real, contada como «duplicada»). **Categoria:** perda de dados. **Estado:** confirmado.
- **Onde:** `backend/importador_transacoes.py:48-58`.
- **Prova:** caso 3: a primeira importação dá 2 inseridas e a reimportação 2 duplicadas (está certo). Caso 4: um ficheiro com 3 cafés iguais, com 2 já na BD, dá `{'inseridas': 0, 'duplicadas': 3}`.
- **Opções:**
  - (a) Comparar contagens (um `Counter`): insere-se cada linha que aparece mais vezes no ficheiro do que na BD.
  - (b) Manter como está e documentar a regra na interface.

### 3.3 Só se aceita CSV em UTF-8

Muitos bancos exportam CSV em Windows-1252 ou ISO-8859-1. Com um ficheiro desses, a pré-visualização dá uma mensagem técnica em inglês. Ao criar o perfil, a análise do ficheiro dá erro 500.

- **Resolvido:** em `10b9157`, com as opções (a) e (c). O CSV lê-se em UTF-8 e, se falhar, em Windows-1252. Se nenhuma servir, a pré-visualização, a importação e a análise do ficheiro respondem 400 com uma mensagem em PT-PT. Um ficheiro numa terceira codificação entraria com os acentos trocados, sem erro.
- **Gravidade:** média. **Categoria:** robustez. **Estado:** confirmado.
- **Onde:** `backend/parser_importacao.py:83` e `backend/routers/perfis_importacao.py:47`, ambos com `decode("utf-8-sig")`.
- **Prova:** caso 2 → `400 'utf-8' codec can't decode byte 0xc1`; caso 2b → `analisar-ficheiro 500 Internal Server Error`.
- **Opções:**
  - (a) Tentar UTF-8 e, se falhar, recorrer a cp1252.
  - (b) Guardar a codificação no perfil.
  - (c) Pelo menos, uma mensagem clara em PT-PT e um 400 em vez de 500.

### 3.4 Não há forma de editar um perfil de importação na interface

O formulário de perfis só cria (`criarPerfil`). As funções `atualizarPerfil` e `associarContaPerfil` existem em `frontend/src/api/perfisImportacao.js`, mas nenhuma página as usa. Para corrigir uma coluna, ou um perfil que perdeu a conta (ver 1.2), é preciso apagá-lo e criá-lo de novo, e a mensagem da importação diz isso mesmo.

- **Gravidade:** baixa. **Categoria:** funcionalidade em falta. **Estado:** confirmado por leitura (encontrado ao corrigir a outra parte do 4.1).
- **Onde:** `frontend/src/pages/Importacao.jsx` (só `criarPerfil`); `backend/routers/perfis_importacao.py` já tem o `PUT` e o `PATCH .../conta`.
- **Opções:**
  - (a) O formulário passa a abrir também em modo de edição, com o `PUT`.
  - (b) Manter: apagar e criar de novo.
- **Resolvido:** com a opção (a). Cada perfil tem um botão ✎ que abre o formulário preenchido e grava com o `PUT`; as colunas mudam-se carregando um ficheiro exemplo. A mensagem da importação de um perfil sem conta diz agora para o editar. `atualizarPerfil` e `eliminarPerfil` chamavam `/perfis-importacao/{id}/`, com barra no fim, a que o backend responde com um redireccionamento (307) para o endereço sem barra. Numa cópia da BD, a pré-verificação CORS e o 307 trazem os cabeçalhos CORS, e o pedido chega ao fim depois do redireccionamento: não era um defeito, só um passo a mais. A barra saiu, para o endereço ser o do router. Verificado com o lint, os testes do backend e pedidos `curl` ao backend numa cópia da BD.

### O que está bem

- **Separador decimal:** tem de ser coerente com o perfil; «12.5» com vírgula decimal é recusado, e os milhares só se aceitam em grupos de 3.
- **Delimitador do CSV:** a detecção escolhe o que dá colunas consistentes e em maior número; um ficheiro ambíguo acaba em erro visível, e não em dados trocados.
- **Tudo ou nada:** com uma linha com erro, nada é escrito; a mensagem indica a primeira linha e a pré-visualização mostra todas.
- **Comissão:** é sempre subtraída, como diz o README.
- **Valores inválidos:** NaN, infinito e valores com símbolo de moeda dão erro e nunca são importados em silêncio.
- **Reimportações e conta:** reimportar o mesmo ficheiro não duplica; a conta do perfil é validada.
- **Resultado:** a interface mostra quantas linhas foram inseridas e quantas eram duplicadas.

## Área 4 — Estatísticas e liquidez

A liquidez pode dar números errados sem aviso em dois casos:

- antes da data de referência de uma conta;
- quando uma conta é desactivada, porque desaparece de todo o histórico.

Além disso, um reembolso numa categoria de receita aparece de forma diferente em cada vista. Tudo foi reproduzido numa BD sintética, `/tmp/rastreio-analise/area4.py`, com uma conta: salário de 1000 e renda de 600 em Janeiro, Fevereiro e Março; saldo de referência de 1000 a 31/03; salário e um reembolso de 200 em Abril.

### 4.1 Antes da data de referência, a conta vale zero na evolução do património

O saldo de cada conta só é calculado para a frente a partir da data de referência; antes dela, a conta não conta. Quem regista o saldo de hoje (o caso natural) e importa o histórico do ano vê a liquidez a zero em todos os meses passados e um salto no mês de referência. O formulário e a página Conceitos não explicam o que a data significa. As transações sem conta (de um perfil sem conta) nunca entram na liquidez, mas entram nas estatísticas.

- **Resolvido:** em `837c038` e `bc2f774` (com `34efd59`, que junta num só sítio o saldo do cartão e o do gráfico). Antes da data de referência, o saldo calcula-se para trás, e um perfil de importação tem sempre uma conta.
- **Gravidade:** alta (números errados sem aviso no gráfico de evolução). **Categoria:** lógica de negócio. **Estado:** confirmado.
- **Onde:** `backend/servicos/patrimonio_serv.py:160-176` (`if conta.data_referencia > data_alvo: continue` e `data > data_referencia`); `frontend/src/pages/Contas.jsx:80-91`.
- **Prova:** evolução da liquidez = `[('2026-01-31', 0.0), ('2026-02-28', 0.0), ('2026-03-31', 1000.0), ('2026-04-30', 2200.0)]`. Calculado à mão para trás: 28/02 = 1000 − (1000 − 600) = 600; 31/01 = 600 − (1000 − 600) = 200.
- **Opções:**
  - (a) Calcular para trás: saldo(d) = saldo de referência − soma das transações em \]d, referência\].
  - (b) Manter o comportamento e explicar no formulário que a data deve ser anterior à primeira transação importada.
  - (c) Avisar quando há transações da conta anteriores à data de referência.

### 4.2 Desactivar uma conta apaga a sua liquidez de todo o histórico

O botão de apagar uma conta com transações desactiva-a. A liquidez só soma as contas activas, para todas as datas. A conta desaparece do património de hoje e da evolução passada, mesmo nos meses em que tinha dinheiro. O aviso ao utilizador diz só «foi desactivada (tem transacções associadas)».

- **Resolvido:** em `bfe60ab`. A liquidez soma todas as contas, activas ou não, e a página Património mostra as desactivadas que ainda têm saldo.
- **Gravidade:** alta (o histórico é reescrito sem aviso). **Categoria:** lógica de negócio. **Estado:** confirmado.
- **Onde:** `backend/servicos/patrimonio_serv.py:162` (`ContaModel.ativa == True`) e `backend/routers/contas.py:46-59`.
- **Prova:** depois de `DELETE conta → {'acao': 'desativada'}`, a evolução fica a zeros em todos os meses (antes estava `1000.0` e `2200.0` em Março e Abril).
- **Opções:**
  - (a) Contar sempre todas as contas: uma conta encerrada tem saldo 0 depois de esvaziada, e o histórico fica certo.
  - (b) Guardar a data de desactivação e só excluir a conta a partir dela.
  - (c) Recusar a desactivação com saldo diferente de zero.

### 4.3 Um reembolso numa categoria de receita aparece como despesa num ecrã e como receita noutro

No resumo mensal, um valor positivo marcado como reembolso numa categoria de receita reduz as despesas. No detalhe mensal e nas médias por categoria, o mesmo valor soma à categoria de receita. Num mês sem outras despesas, as «despesas» ficam positivas (+200). A marca de reembolso só tem efeito em categorias de receita: noutras categorias, um positivo já reduz a despesa, com marca ou sem ela.

- **Resolvido:** em `2f156fc`. A marca de reembolso foi retirada; os totais seguem só o tipo da categoria e o sinal.
- **Gravidade:** média. **Categoria:** lógica de negócio. **Estado:** confirmado.
- **Onde:** `backend/routers/estatisticas.py:321-345` (resumo); `:79-157` e `:280-318` (por categoria e detalhe), que ignoram `reembolso`.
- **Prova:** Abril no resumo: `{'receitas': 1000.0, 'despesas': 200.0, 'poupanca': 1200.0}`; no detalhe: `[('Receita', 'receita', 1200.0)]`.
- **Opções:**
  - (a) Tratar o reembolso da mesma maneira em todas as vistas.
  - (b) Só permitir a marca em transações de categorias de despesa.
  - (c) Retirar a marca e tratar um reembolso como um positivo numa categoria de despesa, que é o que já acontece.

### Decisão a rever: categorias predefinidas «Património» e «Casa › Prestação»

As categorias predefinidas põem «Património» (imóveis, veículos) com o tipo `despesa`. A compra de um carro entra assim nas despesas e na média mensal, e também como bem no património. O tipo `investimento` existe precisamente para «não distorcer» as despesas. «Casa › Prestação» trata património: cada prestação, juros incluídos, aumenta o custo do imóvel, e a dívida não é modelada. Onde: `backend/dados_iniciais.py:20,55`, `:108-112` e `:137`.

- **Decidido:** «Património» mantém o tipo `despesa`: a compra é dinheiro que saiu, e o utilizador pode mudar o tipo na página Categorias, por isso não vai para o README. «Casa › Prestação» deixa de vir marcada como património nos dois perfis: uma prestação conta só como despesa, e o imóvel regista-se à parte. As categorias de quem já as tem não mudam.

### O que está bem

- **Transferências:** são excluídas de todas as vistas de estatísticas.
- **Poupança:** é receitas mais despesas; o investimento fica à parte, como diz a página Conceitos.
- **Estornos de receita:** um negativo numa categoria de receita reduz as receitas.
- **Médias e medianas por categoria:** usam os mesmos meses, com zeros nos meses sem movimentos, e são calculadas em `Decimal`. Está conforme a decisão do README.
- **Totais por categoria:** são somados em cêntimos inteiros, por isso não acumulam erro de `float`.
- **Saldo da conta:** a referência é o saldo no fim do dia de referência; as transações desse dia não contam. É coerente e está em docs/modelo-dados.md, mas a interface não o explica.

## Área 5 — Ativos, FIFO e património

O FIFO e a avaliação dos bens estão certos: os números bateram ao cêntimo com as contas feitas à mão. Os achados são menores.

**Prova do FIFO** (`/tmp/rastreio-analise/area5.py`):

- Operações: compra de 10 unidades a 100 € com 1 € de comissão; compra de 10 a 120 € com 1 €; venda de 15 a 130 € com 1 €.
- Esperado: custo vendido = 1001 + 1201 × 5/10 = 1601,50; realizado = 1949 − 1601,50 = 347,50; restam 5 unidades com custo 600,50, que ao preço de 120 valem 600,00 (latente −0,50).
- Obtido: `quantidade 5.0, custo_total -600.5, valor_atual 600.0, realizado 347.5, latente -0.5`.
- Uma venda de 6 unidades no dia seguinte é recusada com 422: «excede as 5 unidades em carteira».
- Bem sem unidades (um carro comprado por 20000 e avaliado em 17000): `valor_atual 17000, latente -3000`.

### 5.1 Não se consegue apagar o símbolo de um ativo

Quando se apaga o símbolo na edição, o frontend envia `null`. O backend lê `null` como «não alterar», e o símbolo antigo fica.

- **Gravidade:** baixa. **Categoria:** correcção (incoerência entre o frontend e o backend). **Estado:** confirmado.
- **Onde:** `frontend/src/pages/Ativos.jsx:92` e `backend/routers/patrimonio.py:80-83`.
- **Prova:** `/tmp/rastreio-analise/area1.py` → `PUT simbolo=None -> simbolo = TSTX`.
- **Opções:**
  - (a) O backend usa `model_fields_set`, como já faz o `PUT` de transações.
  - (b) O frontend envia "" e o backend converte "" em `NULL`.
- **Resolvido:** com a opção (a). O `PUT` de um ativo muda o símbolo sempre que o campo vem no pedido, também com `null`; um campo omitido fica como estava. Mutações: o código antigo e mudar sempre, ambos mortos.

### 5.2 O campo `moeda` dos ativos é guardado mas não tem efeito

Todos os ativos são criados com «EUR» e nenhum cálculo lê a moeda. Um ativo cotado noutra moeda tem de ter os preços escritos já em euros, e a interface não o diz.

- **Gravidade:** baixa. **Categoria:** estrutura / documentação. **Estado:** confirmado: nenhum uso em `backend/routers` nem em `backend/servicos`, e o frontend envia sempre "EUR" (`Ativos.jsx:125`).
- **Opções:**
  - (a) Documentar que tudo é em euros.
  - (b) Retirar o campo, o que obriga a migração (ver 1.1).
  - (c) Suportar a conversão, que é uma funcionalidade nova.
- **Resolvido:** com a opção (a). As «Limitações» do README dizem que tudo é em euros, e o preço na janela «Actualizar preço» dos ativos diz «em euros». O campo `moeda` fica na BD, sem uso.

### 5.3 O preço de uma venda não actualiza a cotação

Uma compra regista o preço unitário como cotação nesse dia; uma venda não. Depois de vender a 130, as unidades que restam continuam avaliadas a 120, o preço da última compra.

- **Gravidade:** baixa. **Categoria:** lógica de negócio. **Estado:** confirmado (no resumo acima, `preco_atual 120.0` e `data_preco 2026-02-10`).
- **Onde:** `backend/routers/patrimonio.py:139-156`.
- **Opções:**
  - (a) Registar também o preço das vendas.
  - (b) Manter como está e lembrar o utilizador de actualizar a cotação.
- **Resolvido:** com a opção (a). Uma venda com preço regista-o como cotação do dia, como uma compra; um dividendo não, e uma venda recusada também não. O teste que fixava o comportamento antigo passou a fixar o novo.

### O que está bem

- **Comissões:** entram no custo das compras e saem do encaixe das vendas; os rótulos do formulário dizem «sem comissão».
- **Sobre-venda:** é recusada pela ordem do FIFO, ao criar uma venda e ao apagar uma compra.
- **Cálculos em `Decimal`:** o custo de cada lote só é dividido ao ser consumido.
- **Bens sem unidades:** valem o último preço registado ou, sem preço, o custo; uma venda vende tudo, conforme a decisão do README.
- **Evolução:** os pontos passados usam o preço dessa data; os preços futuros são recusados.
- **Pendentes:** são as transações de subcategorias com património que ainda não têm movimento.
- **Ativo apagado:** leva os seus movimentos e preços, e as transações voltam a ficar pendentes.
- **Dividendos:** entram só nas mais-valias realizadas, e não no valor do património, por isso não são contados duas vezes com a liquidez.

## Área 6 — Backups e restauro

O restauro é cuidadoso: valida antes de trocar, troca de forma atómica e repoé a BD anterior se algo falhar. Há, no entanto, dois achados:

- um backup de uma versão anterior é recusado e não há forma de o recuperar;
- um backup com valores inválidos é aceite e parte a aplicação.

Tudo foi reproduzido em `/tmp/rastreio-analise/area6.py`.

### 6.1 Um backup de uma versão anterior é recusado sem explicação

O restauro exige todas as colunas do modelo actual. Um backup feito antes de uma coluna nova ser acrescentada é recusado com «O ficheiro não corresponde a um backup válido do Rastreio-DB». Ninguém o pode migrar, porque não há migrações (ver 1.1). O utilizador fica com um backup legítimo que a aplicação diz ser inválido.

- **Resolvido:** com as opções (a) e (b). Em `cf92195`, as migrações correm no ficheiro restaurado antes da validação, mas só cobrem as mudanças de schema daqui para a frente. Depois, a mensagem passou a distinguir os dois casos: um ficheiro com as tabelas `transacoes`, `categorias` e `contas` a que falta outra coisa é «um backup de uma versão anterior do Rastreio-DB» que «já não pode ser actualizado»; sem uma dessas três, fica a mensagem genérica. Ver também o 6.4.
- **Gravidade:** média. **Categoria:** perda de dados / robustez. **Estado:** confirmado.
- **Onde:** `backend/routers/backups.py:69-100` e `:15-21` (a mensagem é genérica de propósito).
- **Prova:** a cópia sem `coluna_fee` dá `400 'O ficheiro não corresponde a um backup válido do Rastreio-DB'`.
- **Opções:**
  - (a) Aplicar as migrações ao ficheiro restaurado, o que depende da opção escolhida em 1.1.
  - (b) Distinguir na mensagem «backup de uma versão anterior» de «ficheiro que não é do Rastreio-DB».

### 6.2 Um backup com valores inválidos é aceite e deixa a aplicação em erro

A validação confirma as tabelas e as colunas, mas não os valores. Um tipo de categoria desconhecido («poupanca») passa, e a seguir as transações, as categorias e as estatísticas dão erro 500. Também não é corrido o `foreign_key_check`. Só acontece com um ficheiro editado à mão ou estranho; pode recuperar-se restaurando outra vez.

- **Gravidade:** baixa. **Categoria:** robustez. **Estado:** confirmado.
- **Onde:** `backend/routers/backups.py:52-100`; as enumerações não têm `CHECK` na BD (`backend/database.py`).
- **Prova:** `backup com tipo='poupanca' -> 200`; depois, `GET /api/categorias/`, `/api/estatisticas/resumo-mensal` e `/api/transacoes/` dão 500.
- **Opções:**
  - (a) Validar os valores das enumerações e correr `PRAGMA foreign_key_check` antes da troca.
  - (b) Abrir o ficheiro com o ORM e ler uma amostra de cada tabela antes de o aceitar.

### 6.3 Só há uma cópia de segurança automática, substituída em cada restauro

O `.anterior` é reescrito em cada restauro. Quem restaura o ficheiro errado e depois tenta outro perde a BD original. A interface avisa disto («até ao próximo restauro»), mas não oferece forma de repor o `.anterior`: é preciso ir à pasta à mão.

- **Gravidade:** baixa. **Categoria:** perda de dados. **Estado:** confirmado por leitura.
- **Onde:** `backend/routers/backups.py:110-133` e `frontend/src/pages/Transacoes.jsx:43-48`.
- **Opções:**
  - (a) Guardar as cópias com data e hora e manter as N mais recentes.
  - (b) Um botão «desfazer último restauro».
  - (c) Deixar como está, já que o aviso existe.
- **Resolvido:** com a opção (a), com 5 cópias. Cada restauro guarda a BD substituída em `rastreio.db.anterior-AAAA-MM-DD-HHMMSS` (com `-2`, `-3` no mesmo segundo) e apaga as mais antigas, para ficarem 5. A cópia `.anterior` sem data, de versões anteriores, não é tocada. Repor uma cópia continua a ser à mão.

### 6.4 O restauro recusa um backup a que só falta uma tabela nova

Encontrado ao corrigir o 6.1. Uma tabela nova não tem migração, porque no arranque o `create_all` cria-a (é o que diz o `AGENTS.md`). Mas o restauro só aplica as migrações ao ficheiro e não corre o `create_all`. Um backup feito antes de uma tabela nova é recusado, quando bastaria criar essa tabela vazia. Com o 6.1, a recusa diz que o backup «já não pode ser actualizado», o que neste caso não é verdade. Ainda não aconteceu: nenhuma tabela foi acrescentada desde que há migrações.

- **Gravidade:** baixa. **Categoria:** perda de dados / robustez. **Estado:** confirmado por leitura.
- **Onde:** `backend/routers/backups.py` (`importar_backup`: `aplicar_migracoes` e depois `_validar_estrutura`, sem `create_all`) e `backend/database.py` (`criar_tabelas`).
- **Opções:**
  - (a) No restauro, criar no ficheiro temporário as tabelas em falta (o `create_all` com um engine para esse ficheiro) antes de validar.
  - (b) Corrigir só o `AGENTS.md`: uma tabela nova também precisa de migração, para os backups.
- **Resolvido:** com a opção (a). No restauro, antes das migrações e da validação, o temporário ganha, vazias, as tabelas do modelo que lhe faltam (o `create_all`, como no arranque), mas só se tiver `transacoes`, `categorias` e `contas`; noutro SQLite, não se cria nada e a recusa é a genérica. O teste que apagava uma tabela de cada vez passou a dois: sem uma das três de sempre, recusa; sem uma das outras oito, aceita e cria-a vazia. A ordem «tabelas, depois migrações» não é distinguida pelos testes: com as migrações de hoje, as duas ordens dão o mesmo (mutante equivalente).

### O que está bem

- **Validação antes da troca:** o ficheiro é escrito num temporário, com `fsync`, e validado (SQLite, `integrity_check`, tabelas e colunas) antes de a BD actual ser tocada.
- **Troca e rollback:** a troca usa `os.replace` (atómico); se a verificação depois da troca ou a reparação de `ativos_old` falharem, a BD anterior é reposta.
- **`.anterior`:** só é substituído por uma cópia completa, e nunca por um restauro recusado.
- **Exportação:** faz um checkpoint antes de enviar o ficheiro.

## Área 7 — Segurança e robustez do servidor local

Qualquer site aberto no browser pode mandar a API local restaurar a BD ou importar transações: o servidor não verifica de onde vêm os pedidos. Isto pesa numa aplicação pensada para outras pessoas. O servidor só escuta em `127.0.0.1`, o que está bem, mas não basta.

### 7.1 Outro site pode restaurar a BD ou importar transações (CSRF)

Os browsers enviam formulários `multipart/form-data` e `POST` sem corpo para outro endereço sem pedir licença antes («simple requests»); o CORS só impede a página de ler a resposta. O servidor não verifica o `Origin` nem nenhum token. Uma página maliciosa, aberta enquanto a aplicação corre, pode:

- substituir a BD por um ficheiro seu (dois restauros seguidos apagam também o `.anterior`, ver 6.3);
- injectar transações com `/importacao/importar`;
- correr `/configuracao/inicializar`.

As rotas JSON estão protegidas, porque o FastAPI recusa JSON enviado como `text/plain`. As versões recentes do Chrome pedem permissão antes de um site público aceder a `localhost`, mas isso não é garantido em todos os browsers.

- **Resolvido:** em `19ad315`. Um middleware recusa com 403 as escritas cujo `Origin` não seja o da própria aplicação (opção a).
- **Gravidade:** alta. **Categoria:** segurança. **Estado:** do lado do servidor, confirmado; o comportamento do browser segue as regras de CORS e não foi testado num browser.
- **Onde:** `backend/main.py:162-168` (CORS só em dev, e só limita leituras), `backend/routers/backups.py:96`, `backend/routers/importacao.py:41` e `backend/routers/configuracao.py:18`.
- **Prova:** `/tmp/rastreio-analise/area7.py` com `Origin: https://site-malicioso.example`:
  - restauro multipart → `200 'Base de dados restaurada'`;
  - `POST` sem corpo → 200;
  - JSON como `text/plain` → 422 (protegido).
- **Opções:**
  - (a) Um middleware que recusa pedidos de escrita cujo `Origin` (ou `Referer`) não seja o próprio servidor. É simples e cobre todas as rotas.
  - (b) Exigir um cabeçalho próprio (por exemplo `X-Rastreio: 1`) no `client.js`; um site alheio não o consegue enviar sem pedir licença antes.
  - (c) Um token por sessão gerado no arranque. É mais forte, mas mais complexo.

### 7.2 O servidor responde a qualquer nome de anfitrião (DNS rebinding)

Não há validação do cabeçalho `Host`. Com DNS rebinding, um site pode passar a ter o mesmo «origin» que a API e ler todos os dados financeiros. Isto vai além do 7.1, que só permite escrever.

- **Resolvido:** em `59aab1f`. `TrustedHostMiddleware` com `localhost` e `127.0.0.1`.
- **Gravidade:** média. **Categoria:** segurança. **Estado:** é confirmado que o servidor aceita qualquer `Host`; o ataque completo não foi reproduzido.
- **Onde:** `backend/main.py` (sem `TrustedHostMiddleware`).
- **Prova:** `GET /api/transacoes/` com `Host: rebind.site-malicioso.example` → 200, com dados.
- **Opções:**
  - (a) `TrustedHostMiddleware` com `localhost` e `127.0.0.1`. São 2 linhas e resolvem também parte do 7.1.

### 7.3 Com a porta 9742 ocupada, a aplicação parece arrancar mas não serve nada

Se a porta estiver ocupada, o uvicorn sai com `sys.exit(1)` dentro da thread. O `except Exception` não apanha `SystemExit`, por isso «Servidor caiu» nunca fica no log. A janela de controlo abre na mesma, e o browser abre o que estiver na porta (outra instância ou outro programa).

- **Gravidade:** baixa. **Categoria:** robustez. **Estado:** confirmado fora do executável, com uma porta aleatória ocupada (`/tmp/rastreio-analise/area7b.py`): `thread do servidor terminou: True | started: False`, e 0 linhas «Servidor caiu» no log.
- **Onde:** `backend/main.py:249-256` e `:210` (porta fixa).
- **Opções:**
  - (a) Testar a porta no `_preflight` e, se estiver ocupada, abrir o browser na instância existente ou mostrar uma mensagem.
  - (b) Apanhar `BaseException` na thread e fechar a janela de controlo.
- **Resolvido:** com a opção (a). Antes do `_preflight`, `quem_esta_na_porta` (em `tray.py`) liga-se à porta: livre, arranca; se responder como o Rastreio-DB (`/api/configuracao/estado`), abre o browser nessa instância e sai; se for outro programa, regista no log e sai com o código 4. Essa mensagem só se vê no log até ao 7.4. Testado com servidores locais e contra o backend numa cópia da BD; os ramos do `_main` não correram num executável.

### 7.4 No executável, um erro no arranque não se vê: a aplicação simplesmente não abre

Encontrado ao corrigir o 1.1. No modo `--windowed` não há consola. Quando o `_preflight` falha (pasta de dados sem permissões, ou uma BD que o arranque recusa porque lhe faltam colunas), a mensagem só vai para o log de arranque (`arranque.log` em `%LOCALAPPDATA%\rastreio-db\` ou `~/.rastreio-db/`) e o processo sai com o código 2 ou 3. Isto acontece antes de a janela de controlo abrir, por isso o utilizador não vê janela nem aviso, e não sabe que existe um log. A mensagem clara do 1.1 fica onde ninguém a lê.

- **Gravidade:** baixa. **Categoria:** robustez / apresentação. **Estado:** confirmado por leitura.
- **Onde:** `backend/main.py:223-243` (`_preflight`: `_log` e `sys.exit(2)` / `sys.exit(3)`) e `:65` (`LOG_ARRANQUE`).
- **Opções:**
  - (a) Mostrar a mensagem numa caixa de diálogo do tkinter antes de sair, se o tkinter existir (a janela de controlo já o usa).
  - (b) Abrir o browser numa página de erro servida por um servidor mínimo.
  - (c) Deixar como está e explicar no README onde fica o log.
- **Resolvido:** com a opção (a). Os quatro erros do arranque (pasta de dados, base de dados, porta ocupada por outro programa e erro inesperado) passam por `_sair_com_erro`, que regista no log, mostra a mensagem numa caixa de diálogo do tkinter, com o caminho do log, e sai com o mesmo código. Sem tkinter ou sem ecrã, fica só o log. Testado com o tkinter simulado e sem ecrã; a caixa não foi vista num executável.

### O que está bem

- **Rede:** o servidor só escuta em `127.0.0.1`.
- **CORS:** não tem `*`; em dev aceita só `localhost:9743`.
- **Rotas JSON:** não aceitam corpos `text/plain`, por isso não são vulneráveis a CSRF.
- **Arranque:** os erros na pasta de dados e na criação das tabelas ficam no log, com códigos de saída distintos (2 e 3).
- **Modo `--windowed`:** o stdout e o stderr vão para um ficheiro de log, e não para o vazio.
- **Janela de controlo:** se o tkinter faltar, a aplicação continua sem ela.

## Área 8 — Frontend e apresentação das estatísticas

O cartão «Taxa de poupança» dá uma ideia errada. Nos teus dados, a média das taxas mensais é 42,3% e a mediana 53,9%, mas no conjunto pouparam-se 14,6% das receitas. O resto são achados menores. Esta área foi verificada por leitura do código, pelo `npm run lint` (sem avisos) e por cálculos na cópia da BD. Não houve testes no browser.

### 8.1 A «taxa de poupança» dos cartões é a média das taxas de cada mês, e engana

O cartão calcula a taxa de cada mês e faz a média e a mediana dessas taxas. Cada mês pesa o mesmo, tenha a receita que tiver, e um mês com pouca receita pode dar −118%. O Histórico mostra a taxa anual agregada (soma da poupança a dividir pela soma das receitas). As duas páginas dão assim números muito diferentes para o que parece ser a mesma coisa. Num mês sem receitas, o Histórico mostra «—%» e as Estatísticas deixam um buraco; num ano sem receitas, o Histórico mostra 0%.

- **Resolvido:** em `dd474cc` (e as cores em `dd4c42d`). A taxa do período é a soma da poupança a dividir pela soma das receitas, com a mediana mensal como dado secundário.
- **Gravidade:** alta (um número três vezes acima do real, sem aviso). **Categoria:** lógica de negócio / apresentação. **Estado:** confirmado na cópia da BD real.
- **Onde:** `frontend/src/pages/Estatisticas.jsx:82` e `:115-130`; `frontend/src/pages/Historico.jsx:35`.
- **Prova:** `/tmp/rastreio-analise/area8.py`, 29 meses → média das taxas mensais = 42,3%; mediana = 53,9%; agregada (soma da poupança / soma das receitas) = 14,6%; mínimo e máximo mensais = −117,8% e 87,7%.
- **Opções:**
  - (a) O cartão mostra a taxa agregada do período e mantém a mediana mensal como informação secundária.
  - (b) Uma média ponderada pela receita, que dá o mesmo número que a agregada.
  - (c) Manter o cálculo e explicar no cartão o que é.

### 8.2 Decisão a rever: o mês em curso e os meses incompletos entram nas médias

O último mês com dados (Setembro de 2026, com transações só até dia 7) conta como um mês inteiro nas médias e medianas, no gráfico e nos cartões. Nos teus dados, as despesas desse mês são 9% das de um mês típico e baixam a média de despesas em 3,1%. A decisão do README sobre «meses com transações» cobre os meses com só transferências, mas não os meses incompletos.

- **Gravidade:** média. **Categoria:** lógica de negócio. **Estado:** confirmado (mesma sonda).
- **Onde:** `backend/routers/estatisticas.py:17-67` e `:79-157`; `frontend/src/pages/Estatisticas.jsx:112-131`.
- **Opções:**
  - (a) Excluir o mês em curso das médias.
  - (b) Marcá-lo como «incompleto» no gráfico.
  - (c) Manter e documentar.
- **Resolvido:** com a opção (c). O cálculo fica igual, e a decisão está no README, em «Decisões de design».

### 8.3 Erros da API passam em silêncio em várias páginas

Várias chamadas não têm `catch`. Exemplos:

- a edição inline na tabela de transações (ver 2.1);
- apagar uma regra;
- as páginas Estatísticas, Histórico e Património, que usam `.then` sem `catch` e ficam em «A carregar...» para sempre se o backend falhar.
- **Gravidade:** baixa. **Categoria:** robustez. **Estado:** confirmado por leitura.
- **Onde:** `components/TabelaTransacoes.jsx` (6 `await`, nenhum `catch`), `pages/Patrimonio.jsx:21`, `pages/Estatisticas.jsx:62-68` e `pages/Regras.jsx:66-70`.
- **Opções:**
  - (a) Um interceptor no `client.js` que mostra o `detail` de qualquer erro.
  - (b) Um `catch` em cada chamada.

### 8.4 A média e a mediana mensais calculadas no backend não são usadas

`/estatisticas/resumo-mensal` devolve `media_mensal` e `mediana_mensal`, calculadas em `Decimal`. O frontend ignora-as e recalcula tudo em `float` a partir dos meses. São dois sítios com a mesma regra.

- **Gravidade:** baixa. **Categoria:** qualidade. **Estado:** confirmado (nenhuma referência a estes campos em `frontend/src`).
- **Opções:**
  - (a) Retirar os campos do backend.
  - (b) O frontend passa a usá-los e o backend aceita o filtro por ano.
- **Resolvido:** com a opção (a). `/estatisticas/resumo-mensal` devolve só `{"meses": [...]}`; a média e a mediana ficam só na página. Saiu também o teste do meio cêntimo destes dois campos.

### 8.5 No detalhe do Histórico, cada subcategoria de receita mostra o total da categoria

Ao abrir um mês no Histórico, as linhas das subcategorias de receita repetem o total da categoria em vez do seu próprio valor. Em Julho de 2026, «Salário» e «Juros» aparecem ambas com 4 094,52 €, quando os valores reais são 4 086,71 € e 7,81 €. As colunas de despesa e de investimento usam o valor da subcategoria e estão certas.

- **Gravidade:** média (um valor errado à vista). **Categoria:** correcção. **Estado:** confirmado na cópia da BD real (`detalhe_mensal` de 2026-07 e 2025-10).
- **Onde:** `frontend/src/pages/Historico.jsx:109` (`cat.total` em vez de `sub.total`).
- **Opções:**
  - (a) Usar `sub.total`, como nas outras colunas.
- **Resolvido:** com a opção (a). Cada subcategoria de receita mostra o seu próprio valor. Verificado com o lint; não testado no browser.

### 8.6 A taxa anual do Histórico perde a casa decimal quando termina em zero

A taxa de cada ano passa por `parseFloat(... .toFixed(1))`, que tira o zero final: aparece «−89%» em 2024, enquanto os meses mostram sempre uma casa decimal (por exemplo «52,0%»).

- **Gravidade:** baixa. **Categoria:** apresentação. **Estado:** confirmado por leitura e na cópia da BD real.
- **Onde:** `frontend/src/pages/Historico.jsx:35` e `:76`.
- **Opções:**
  - (a) Guardar o número sem `toFixed` e formatar com `.toFixed(1)` só ao mostrar, como nos meses.
- **Resolvido:** com a opção (a). A taxa anual guarda-se sem arredondar e mostra-se com `.toFixed(1)`, como a dos meses («−89,0%»). Verificado com o lint; não visto no browser.

### O que está bem

- **Formatação:** os valores usam `Intl.NumberFormat('pt-PT')`, com milhares e duas casas decimais.
- **Campos numéricos:** são `type="number"`, por isso a vírgula decimal é tratada pelo browser.
- **Valores extremos:** quando a escala do gráfico os corta, há um aviso explícito e um botão para os incluir.
- **Taxa sem receitas:** num mês sem receitas, as Estatísticas não inventam uma taxa (fica um buraco).
- **Transações por categorizar:** o contador na barra lateral mostra quantas ficam de fora das estatísticas.
- **Chamadas à API:** todas passam pelo `client.js`, como diz o AGENTS.md.

## Área 9 — Testes

A suite é sólida: é isolada da BD real, os valores esperados são calculados à mão e matou 5 de 8 mutações em pontos críticos. Os 3 mutantes que sobreviveram coincidem com três achados das áreas anteriores: o comportamento em causa não está fixado por nenhum teste.

**Mutações** (`/tmp/rastreio-analise/mutar.py`, cada uma numa cópia limpa em `/tmp/rastreio-analise/mut/`, sem `__pycache__`, com a alteração confirmada no ficheiro):

| Mutante | Resultado | Resumo do pytest |
| --- | --- | --- |
| M1 importação: `abs(crédito) − abs(débito)` | sobreviveu | 359 passed |
| M2 duplicados sem o saldo na chave | morto | 3 failed, 356 passed |
| M3 liquidez a contar contas inactivas | sobreviveu | 359 passed |
| M4 liquidez antes da data de referência | morto | 1 failed, 358 passed |
| M5 restauro sem validação prévia da estrutura | morto | 6 failed, 353 passed |
| M6 reembolso ignorado em receitas | sobreviveu | 359 passed |
| M7 FIFO passa a LIFO | morto | 5 failed, 354 passed |
| M8 exclusões deixam de ganhar às outras regras | morto | 1 failed, 358 passed |

### 9.1 Há três comportamentos críticos que nenhum teste fixa

Nenhum dos três mutantes que sobreviveram é equivalente: cada um muda o resultado para um utilizador real.

- **M1:** nenhum teste importa um extracto com o débito negativo (achado 3.1).
- **M3:** nenhum teste verifica o que acontece à liquidez quando uma conta é desactivada (achado 4.2).
- **M6:** nenhum teste põe um reembolso positivo numa categoria de receita, apesar de a docstring de `test_estatisticas_totais.py` falar do «sinal do reembolso» (achado 4.3).

Qualquer correcção destes achados pode assim mudar o comportamento sem que um teste o assinale.

- **Gravidade:** média. **Categoria:** qualidade (testes). **Estado:** confirmado pela tabela acima.
- **Opções:**
  - (a) Antes de cada correcção, um teste que fixa o comportamento actual; depois, o teste muda com a correcção.
  - (b) Só acrescentar os testes junto com as correcções.
- **Resolvido:** com a opção (b), nas correcções do 3.1 (`5f639a2`), do 4.2 (`bfe60ab`) e do 4.3 (`2f156fc`), cada uma com o seu teste. Mutações repetidas numa cópia, sem a BD: sem mutação, 413 passed; M1 (`credito - debito`) morto, 1 failed, 412 passed; M3 (a liquidez só com as contas activas) morto, 1 failed, 412 passed; com o código reposto, 413 passed. O M6 já não existe, porque a marca de reembolso foi retirada no 4.3; a variante mais próxima, M6' (um positivo numa categoria de receita deixa de contar como receita), morre com 5 failed, 408 passed.

### 9.2 Faltam testes nas fronteiras entre partes

O 400 do achado 2.1 está fixado como intencional, mas nenhum teste cobre a sequência de pedidos que o frontend envia. Não há teste da origem dos pedidos (7.1), nem do executável empacotado (um arranque mínimo do PyInstaller). O frontend não tem testes, o que está documentado no AGENTS.md.

- **Gravidade:** baixa. **Categoria:** qualidade (testes). **Estado:** confirmado por pesquisa: 0 ficheiros de teste com `Origin`/`csrf` ou `TrustedHost`.
- **Opções:**
  - (a) Um teste de API que reproduz cada fluxo do frontend que é crítico.
  - (b) Na CI, um passo que arranca o executável gerado e faz um `GET /api/configuracao/estado`.

### O que está bem

- **Isolamento:** `conftest.py` define `RASTREIO_DB_DIR`, `HOME` e `LOCALAPPDATA` antes de qualquer import, e `test_seguranca_bd.py` falha se essa ordem se inverter.
- **App de testes:** é montada a partir dos routers, e um teste garante que a lista é igual à do `main.ROUTERS`.
- **Valores esperados:** são constantes com o cálculo em comentário (amostra verificada em `test_patrimonio_fifo.py`) e usam os enums reais.
- **Cobertura:** 359 testes (310 funções mais parametrizações), com cobertura densa de FIFO, importação, regras, estatísticas e backups.
- **Velocidade:** a suite corre em cerca de 6 s, sem depender da data de hoje (`filterwarnings` e datas fixadas).

## Área 10 — Build, CI, empacotamento e dependências

As dependências estão fixadas e o build é reprodutível. Os problemas estão em requisitos mal documentados (que impedem o build) e em releases que não passam pelos testes.

### 10.1 Os requisitos de Python e de Node nos documentos impedem o build

- O `WINDOWS.md` pede «Python 3.11 ou superior», mas `database.py:84` usa `except AttributeError, OSError:`, uma sintaxe que só existe a partir do Python 3.14. Com 3.11 a aplicação nem arranca.
- O `WINDOWS.md` e o `docs/desenvolvimento.md` pedem «Node.js 18 ou superior», mas o Vite 8 exige Node `^20.19.0 || >=22.12.0`.
- **Gravidade:** média (quem segue os documentos fica com um build partido). **Categoria:** documentação. **Estado:** confirmado.
- **Prova:** `python3.11 -c "import ast; ast.parse(open('database.py').read())"` → `SyntaxError: multiple exception types must be parenthesized`. Os `engines` do Vite instalado: `{ node: '^20.19.0 || >=22.12.0' }`.
- **Opções:**
  - (a) Corrigir os documentos para Python 3.14 e Node 20.19 ou superior.
  - (b) Acrescentar `engines` ao `package.json` e `requires-python` ao backend, para o erro aparecer cedo.
- **Resolvido:** com as opções (a) e (b). O `WINDOWS.md` e o `docs/desenvolvimento.md` pedem Python 3.14 e Node 22.12 (ou 20.19, no 20); o `frontend/package.json` tem os mesmos `engines` do Vite, e o novo `backend/pyproject.toml` só declara `requires-python = ">=3.14"`. O `npm install` só avisa sobre o `engines`, e o `requires-python` não tem efeito com `pip install -r requirements.txt`; ficam como documentação que as ferramentas lêem.

### 10.2 Uma release pode sair sem os testes terem passado

O `build.yml` corre quando se cria uma tag e não tem nenhum passo de testes nem de lint. O `test.yml` não corre em tags. Uma tag num commit cuja CI falhou, ou que nunca correu, gera e publica executáveis na mesma. Além disso, o trabalho do Linux depende do do Windows (`needs: build-windows`): uma falha no Windows impede a release de Linux.

- **Gravidade:** média. **Categoria:** estrutura (CI). **Estado:** confirmado por leitura de `.github/workflows/build.yml` e `test.yml`.
- **Opções:**
  - (a) Chamar o `test.yml` a partir do `build.yml` (`workflow_call`) e pôr os builds a depender dele.
  - (b) Correr pelo menos `pytest` antes do build em cada sistema.
  - (c) Tirar o `needs` entre o Windows e o Linux.
- **Resolvido:** com as opções (a) e (c). O `build.yml` chama o `test.yml` (`workflow_call`), e os dois builds dependem só dele e correm em paralelo: uma tag num commit com a CI a falhar não gera release. Para os dois não criarem a mesma release ao mesmo tempo, guardam os ficheiros e um trabalho final, `publicar`, cria a release com os dois anexos; se um build falhar, não sai nenhuma. Verificado com um parser de YAML; não testado no GitHub.

### 10.3 A aplicação não mostra a sua versão

Não há versão em nenhum sítio: o `package.json` diz `0.0.0`, e nem o `main.py` nem a página Sobre mostram uma. Quem usa não sabe que versão tem, o que pesa quando houver migrações (1.1) ou quando alguém reportar um problema.

- **Gravidade:** baixa. **Categoria:** estrutura. **Estado:** confirmado: nenhuma ocorrência de «versão» ou «version» em `Sobre.jsx`, `App.jsx` ou `main.py`.
- **Opções:**
  - (a) Escrever a tag no build (variável de ambiente ou ficheiro) e mostrá-la na página Sobre e num `GET /api/versao`.

### 10.4 O `pyinstaller` está nas dependências de produção

O `requirements.txt` inclui `pyinstaller`, `pyinstaller-hooks-contrib` e `setuptools`. O comentário do `requirements-dev.txt` diz que o `requirements.txt` é o que o executável leva. O `build.sh` e o `build.bat` instalam o `pyinstaller` de novo, à parte e sem versão. Não tem efeito no executável, mas mistura as dependências de build com as de execução.

- **Gravidade:** baixa. **Categoria:** estrutura. **Estado:** confirmado (`backend/requirements.txt:13-16`, `build.sh:36`, `build.bat:44`).
- **Opções:**
  - (a) Um `requirements-build.txt` com o `pyinstaller` fixado, usado pelos scripts de build.

### Suspeito, por confirmar

- O executável de Linux é gerado em `ubuntu-latest` e pode exigir uma glibc mais recente do que a de distribuições mais antigas. Não testei.

### O que está bem

- **Dependências fixadas:** o backend fixa todas as versões, e o frontend usa `npm ci` com `package-lock.json`.
- **Mesmos scripts:** a CI corre os mesmos `build.sh` e `build.bat` que se usam localmente.
- **Verificações da CI:** a CI de testes corre `ruff`, `pyright`, `pytest` e o `eslint` com `--max-warnings 0`, como pede o AGENTS.md.
- **PyInstaller em `--onedir`:** a pasta `dados/` fica fora do bundle e é criada vazia; o build não leva nenhuma BD.
- **`.gitignore`:** exclui as BDs, os `.anterior`, os `.xlsx` e as pastas de build.

## Área 11 — Documentação, AGENTS.md e organização

O `docs/modelo-dados.md` está certo e é útil. Os outros documentos têm erros que levam a passos errados. O mais sério é que a regra de segurança do AGENTS.md não protege a BD real quando se corre um script de migração.

### 11.1 Os scripts de migração ignoram `RASTREIO_DB_DIR`, e a regra do AGENTS.md dá uma falsa segurança

O AGENTS.md manda definir `RASTREIO_DB_DIR` antes de correr qualquer script que importe `database`. Três dos oito scripts `migrar_*.py` (`migrar_contas.py`, `migrar_fee.py` e `migrar_patrimonio.py`) não passam por `database`: calculam o caminho da BD a partir da própria pasta e ignoram a variável. Um script novo na raiz do backend, feito com o mesmo padrão, abre `backend/dados/rastreio.db` mesmo com `RASTREIO_DB_DIR` apontado para uma cópia. Os scripts já arquivados em `backend/old/` apontam para `backend/old/dados/`, uma pasta que não existe.

- **Resolvido:** em `e9936b9`. Os scripts já aplicados foram apagados, e as migrações passaram depois para a lista `MIGRACOES` (1.1).
- **Gravidade:** alta (risco directo para a BD real, o que o AGENTS.md quer impedir). **Categoria:** segurança dos dados / documentação. **Estado:** confirmado por leitura (`backend/old/migrar_fee.py:5-10`, com `BASE_DIR` calculado a partir de `__file__`). Não corri nenhum script.
- **Opções:**
  - (a) Os scripts de migração passam a importar `DB_PATH` de `database`, e o AGENTS.md di-lo.
  - (b) Uma regra explícita no AGENTS.md: um script de migração recebe o caminho da BD como argumento e nunca tem um valor por omissão.
  - (c) Embutir as migrações no arranque (opção (a) do 1.1), o que acaba com os scripts soltos.

### 11.2 O AGENTS.md tem instruções que contradizem as suas próprias regras

- «Stack & Ports» mostra `uvicorn main:app --reload --port 9742` sem `RASTREIO_DB_DIR`, o comando que a regra 1 classifica como «wrong». Só a cópia em «Development Commands» tem a ressalva.
- «Stack & Ports» e «Gotchas» dizem que o Vite faz de proxy de `/api`. A regra 4 (e o `client.js:4`) mostram que, em dev, o frontend chama a 9742 directamente, por isso o proxy não é usado. Um agente que confie no proxy pensa que mudar a porta isola o frontend, e não isola.
- **Gravidade:** média. **Categoria:** documentação (AGENTS.md). **Estado:** confirmado por leitura.
- **Opções:**
  - (a) Na «Stack & Ports», só o comando com `RASTREIO_DB_DIR`.
  - (b) Retirar a menção ao proxy, ou passar o `client.js` a usar `/api` também em dev, para o proxy passar a contar. Esta última é uma mudança de código, a decidir.
- **Resolvido:** com a opção (a) e, no proxy, só nos documentos. A «Stack & Ports» mostra o comando com `RASTREIO_DB_DIR`; o `AGENTS.md` e o `docs/desenvolvimento.md` dizem que, em dev, o frontend chama a 9742 directamente e o proxy não é usado. O código fica igual.

### 11.3 Os documentos de instalação e de build têm passos errados

- O `docs/desenvolvimento.md` diz que o executável «abre automaticamente no browser em `http://localhost:9743`». Abre em 9742 (`main.py:210` e `abrir_browser`).
- O `WINDOWS.md` faz `cd backend` e, sem voltar atrás, `cd frontend`, o que falha. O passo 2 é desnecessário, porque o `build.bat` cria o venv. Os requisitos de Python e de Node estão errados (10.1).
- O `docs/arquitectura.md` só refere o `build.yml` na CI e omite o `test.yml`.
- O README não diz a quem descarrega a release como a correr (Windows e Linux), onde ficam os dados, nem como actualizar sem os perder. Isso só aparece nos documentos de quem faz o build.
- **Gravidade:** média (para quem instala ou actualiza, que são as «pessoas que vão usar»). **Categoria:** documentação. **Estado:** confirmado por leitura.
- **Opções:**
  - (a) Uma secção «Instalar e actualizar» no README (descarregar, extrair, correr, manter `dados/`, fazer backup antes de actualizar).
  - (b) Corrigir as quatro incoerências acima.
- **Resolvido:** com as opções (a) e (b). O README tem uma secção «Instalar e actualizar» (descarregar, extrair, correr, onde ficam os dados, e actualizar com um backup e copiando `dados/` para a pasta da versão nova). O `docs/desenvolvimento.md` diz a porta 9742, o `WINDOWS.md` já não tem o passo do venv nem o `cd` que falhava, e o `docs/arquitectura.md` descreve o `test.yml` e a ordem do `build.yml`.

### 11.4 O filtro de avisos do `pytest.ini` nunca se aplica

`filterwarnings = error::DeprecationWarning:backend.*` só apanha módulos cujo nome começa por `backend`. Os módulos são importados como `database`, `routers.…` e `servicos.…` (`pythonpath = .`), por isso o filtro nunca casa. O comentário por cima fala em «data de hoje», que não tem nada a ver com o filtro.

- **Gravidade:** baixa. **Categoria:** qualidade. **Estado:** confirmado: com um `DeprecationWarning` injectado em `servicos/dinheiro.py` numa cópia, a suite dá `359 passed, 319 warnings`, em vez de falhar.
- **Opções:**
  - (a) Mudar para `error::DeprecationWarning:(database|schemas|routers|servicos|importador_transacoes|parser_importacao).*`.
  - (b) Retirar a linha e o comentário.

### 11.5 Ficheiros soltos e restos

- `extensions.txt` na raiz lista extensões do VS Code. O formato que o VS Code lê é `.vscode/extensions.json`, que o `frontend/.gitignore` até prevê.
- O `ruff.toml` exclui `backend/old/`, mas os scripts continuam versionados, com o caminho errado (11.1).
- **Gravidade:** baixa. **Categoria:** estrutura. **Estado:** confirmado.
- **Opções:**
  - (a) Converter para `.vscode/extensions.json`.
  - (b) Decidir se `backend/old/` fica no repositório como histórico ou sai.
- **Resolvido:** o `extensions.txt` foi apagado: é uma preferência pessoal e o VS Code não o lê. A pasta `backend/old/` já tinha saído em `e9936b9` (11.1), e o `ruff.toml` já não a exclui.

### 11.6 O README diz que se pode editar a conta de uma transação

A lista de funcionalidades do README diz «edição inline de categoria, subcategoria, reembolso, conta e notas». A conta não se pode editar: o `TransacaoUpdate` não tem `conta_id`, e a tabela de transações não mostra esse campo como editável.

- **Gravidade:** baixa. **Categoria:** documentação. **Estado:** confirmado por leitura (encontrado ao analisar o 4.3).
- **Onde:** `README.md:18`; `backend/schemas.py` (`TransacaoUpdate`).
- **Opções:**
  - (a) Corrigir o README.
  - (b) Permitir mudar a conta de uma transação, o que também dá uma saída às transações sem conta antigas (ver a outra parte do 4.1).
- **Resolvido:** com a opção (a). O README já não refere a conta na edição inline. Numa cópia da BD, não há transações sem conta (0 de 705).

### O que está bem

- **`docs/modelo-dados.md`:** está certo face ao código (tabelas, convenções de sinal, semântica da data de referência e do reembolso, preços).
- **«Decisões de design» do README:** coincidem com o código, com a excepção das exclusões nas regras (2.2).
- **AGENTS.md:** as regras de segurança da BD, de testes, de mutantes, de git e de lint batem com os scripts e com a CI reais; os stop gates são claros.
- **Estrutura de pastas:** é coerente com a descrita (routers por domínio, `servicos/`, uma página por rota, `api/` por domínio).
- **Contrato entre o frontend e o backend:** os campos estão alinhados, com as excepções 2.1 e 5.1.
- **Referências a análises anteriores:** estão listadas no início deste documento; não há outras nos documentos.

## Estado final da BD real

A BD real nunca foi aberta e está igual ao início: md5 `8e6d8ac8cc48f83e2ab07576f078278f`, 159744 bytes, modificada a 2026-10-19 21:20:40 (Modify e Change iguais). Na pasta `backend/dados/` só está `rastreio.db`, sem `.anterior` nem `.tmp`. O `git status` está limpo e a porta 9742 está livre. Todas as sondas correram em `/tmp/rastreio-analise/`.

- [x] Áreas 0 a 11 analisadas e registadas acima

## Resumo de achados

São 45 achados: 7 de gravidade alta, 13 médios, 24 baixos e 1 tratado como limitação (2.6), além de uma decisão a rever, já decidida (as categorias predefinidas «Património» e «Prestação», na Área 4). Não há nenhum achado crítico em geral. O 3.1 é crítico para quem usa um banco que exporta o débito com sinal. Sugestão de ordem para a fase de correcção: primeiro a segurança e os dados (7.1, 7.2, 11.1, 3.1, 3.2, 4.2), depois os números que se vêem (4.1, 8.1, 4.3) e por fim o resto. A decisão é tua.

**Progresso:** 39 resolvidos (os 7 de gravidade alta, 1.2, 1.3, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 3.2, 3.3, 3.4, 4.3, 5.1, 5.2, 5.3, 6.1, 6.3, 6.4, 7.2, 7.3, 7.4, 8.2, 8.4, 8.5, 8.6, 9.1, 10.1, 10.2, 11.2, 11.3, 11.5 e 11.6). A coluna «Resolução» diz em que commit.

| Nº | Achado | Gravidade | Categoria | Estado | Resolução |
| --- | --- | --- | --- | --- | --- |
| 1.1 | Uma BD de uma versão anterior arranca e depois dá erros 500 | alta | robustez / estrutura | confirmado | `cf92195` |
| 3.1 | Um débito negativo no extracto entra como receita | alta | correcção | confirmado | `5f639a2` |
| 4.1 | Antes da data de referência, a conta vale zero na evolução | alta | lógica de negócio | confirmado | `837c038`, `bc2f774`, `34efd59` |
| 4.2 | Desactivar uma conta apaga a sua liquidez do histórico | alta | lógica de negócio | confirmado | `bfe60ab` |
| 7.1 | Outro site pode restaurar a BD ou importar transações (CSRF) | alta | segurança | confirmado (servidor) | `19ad315` |
| 8.1 | A taxa de poupança dos cartões é uma média de taxas (42% contra 15% reais) | alta | apresentação | confirmado | `dd474cc`, `dd4c42d` |
| 11.1 | Os scripts de migração ignoram `RASTREIO_DB_DIR` | alta | segurança dos dados | confirmado por leitura | `e9936b9` |
| 2.1 | Não se consegue mudar a categoria de uma transação com subcategoria | média | correcção | confirmado (backend), por leitura (frontend) | `b78dcb8` |
| 3.2 | Uma transação igual a outra já importada é descartada | média | perda de dados | confirmado | `58573d4` |
| 3.3 | Só se aceita CSV em UTF-8 | média | robustez | confirmado | `10b9157` |
| 4.3 | Um reembolso numa categoria de receita aparece diferente em cada ecrã | média | lógica de negócio | confirmado | `2f156fc` |
| 6.1 | Um backup de uma versão anterior é recusado | média | perda de dados | confirmado | `cf92195`, resolvido |
| 7.2 | O servidor aceita qualquer `Host` (DNS rebinding) | média | segurança | confirmado em parte | `59aab1f` |
| 8.2 | O mês incompleto entra nas médias (decisão a rever) | média | lógica de negócio | confirmado | decisão documentada no README |
| 8.5 | No detalhe do Histórico, as subcategorias de receita mostram o total da categoria | média | correcção | confirmado | resolvido |
| 9.1 | Três comportamentos críticos sem teste (M1, M3, M6) | média | testes | confirmado | `5f639a2`, `bfe60ab`, `2f156fc` |
| 10.1 | Os requisitos de Python e de Node nos documentos impedem o build | média | documentação | confirmado | resolvido |
| 10.2 | Uma release pode sair sem os testes terem passado | média | CI | confirmado por leitura | resolvido |
| 11.2 | O AGENTS.md contradiz as suas próprias regras | média | documentação | confirmado por leitura | resolvido |
| 11.3 | Os documentos de instalação e de build têm passos errados | média | documentação | confirmado por leitura | resolvido |
| 1.2 | Apagar uma conta tira-a, sem aviso, aos perfis | baixa | correcção | confirmado | `bc2f774`, resolvido |
| 1.3 | Nomes repetidos ou vazios em subcategorias e categorias | baixa | robustez | confirmado | resolvido |
| 2.2 | As exclusões ganham sempre, ao contrário do README | baixa | documentação | confirmado | resolvido |
| 2.3 | A página Conceitos descreve funcionalidades de regras que não existem | baixa | documentação | confirmado | resolvido |
| 2.4 | «Aplicar regras» conta casos sem efeito | baixa | correcção | confirmado | resolvido |
| 2.5 | Uma regra aceita uma subcategoria de outra categoria | baixa | robustez | confirmado | resolvido |
| 3.4 | Não há forma de editar um perfil de importação na interface | baixa | funcionalidade em falta | confirmado por leitura | resolvido |
| 5.1 | Não se consegue apagar o símbolo de um ativo | baixa | correcção | confirmado | resolvido |
| 5.2 | `moeda` é guardado mas não tem efeito | baixa | estrutura | confirmado | resolvido |
| 5.3 | O preço de uma venda não actualiza a cotação | baixa | lógica de negócio | confirmado | resolvido |
| 6.2 | Um backup com valores inválidos é aceite | baixa | robustez | confirmado |  |
| 6.3 | Só há um `.anterior`, substituído em cada restauro | baixa | perda de dados | confirmado por leitura | resolvido |
| 6.4 | O restauro recusa um backup a que só falta uma tabela nova | baixa | perda de dados / robustez | confirmado por leitura | resolvido |
| 7.3 | Com a porta ocupada, a aplicação parece arrancar | baixa | robustez | confirmado | resolvido |
| 7.4 | No executável, um erro no arranque não se vê | baixa | robustez / apresentação | confirmado por leitura | resolvido |
| 8.3 | Erros da API passam em silêncio | baixa | robustez | confirmado por leitura |  |
| 8.4 | A média e a mediana do backend não são usadas | baixa | qualidade | confirmado | resolvido |
| 8.6 | A taxa anual do Histórico perde a casa decimal | baixa | apresentação | confirmado | resolvido |
| 9.2 | Faltam testes nas fronteiras entre partes | baixa | testes | confirmado |  |
| 10.3 | A aplicação não mostra a sua versão | baixa | estrutura | confirmado |  |
| 10.4 | O `pyinstaller` está nas dependências de produção | baixa | estrutura | confirmado |  |
| 11.4 | O filtro de avisos do `pytest.ini` nunca se aplica | baixa | qualidade | confirmado |  |
| 11.5 | Ficheiros soltos e restos | baixa | estrutura | confirmado | resolvido |
| 11.6 | O README diz que se pode editar a conta de uma transação | baixa | documentação | confirmado por leitura | resolvido |
| 2.6 | Não há forma de apagar nem de criar transações | limitação | lógica de negócio | documentado | resolvido |
