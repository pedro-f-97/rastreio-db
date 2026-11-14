# Plano: relatório anual para o IRS (mais-valias, dividendos e juros)

Estado: **passos 1 a 5 executados**. Antes do passo 6 confirmam-se os pontos
da secção 5. Decisões tomadas a 14/11/2026 (secção 4).

Pequenas decisões tomadas durante a execução:

- As compras antigas têm um endpoint próprio, `POST /patrimonio/compras-antigas`,
  em vez de uma regra nova no `POST /patrimonio/movimentos`. O endpoint não tem
  tipo de movimento (cria sempre compras) e recusa campos a mais. O dos
  movimentos continua a aceitar, pela API, movimentos sem transação, como os
  testes de caracterização já fixavam; o ecrã só os cria a partir de uma
  transação.
- Ao corrigir a data de um movimento, o preço que a compra ou a venda gravou
  fica na data em que foi gravado.
- A etiqueta «antiga» só aparece nas compras sem transação.
- O país do ativo edita-se ao lado do nome, e não do símbolo, onde a coluna é
  estreita demais para os dois campos.

## 1. O objectivo

Uma página que, para um ano escolhido, mostra os valores a declarar no IRS
sobre os investimentos e as poupanças:

- as **vendas**, uma linha por lote vendido, com a data e o valor de
  realização, a data e o valor de aquisição, e as despesas;
- os **dividendos** recebidos;
- os **juros** recebidos;
- os totais de cada grupo, para conferir com os documentos anuais da corretora
  e do banco.

O que a página **não** faz:
- não entrega nada nas Finanças;
- não calcula o imposto (decisão 9);
- não substitui o relatório fiscal da corretora nem um contabilista: serve para
  preparar e conferir.

## 2. O que já existe e o que falta

**Já existe:**
- **O FIFO.** O `_resumo_valor_ativo` (`servicos/patrimonio_serv.py`) já
  consome os lotes pela ordem de compra, em `Decimal`. Pelo que sei, o CIRS
  também manda considerar vendidas as unidades compradas há mais tempo (a
  confirmar, secção 5), e por isso a regra é a mesma.
- **As comissões dos ativos com unidades.** Guardam-se à parte, em
  `MovimentoAtivo.comissao`, para além do `valor_total`. Uma compra guarda o
  total com a comissão, e uma venda o total sem ela. Por isso dá para separar
  o valor bruto das despesas.
- **Os dividendos**, como movimentos do tipo `dividendo`.
- **A data do movimento.** O movimento tem a sua própria coluna `data`,
  separada da transação.
- **Os valores em euros**, que é o que se declara.

**Falta:**
1. **O FIFO só devolve somas.** Dá o ganho realizado de todas as vendas
   juntas, mas não diz que lotes cada venda consumiu nem com que datas.
2. **Não há classificação fiscal dos ativos** nem país, nos ativos ou nas
   contas.
3. **Não há forma de reconhecer os juros**: são receitas como as outras.
4. **Não se registam compras anteriores aos extractos.** Um movimento só nasce
   de uma transação por tratar. Um ETF comprado antes do primeiro extracto
   importado não tem lote, e a venda é recusada por exceder as unidades em
   carteira.
5. **A data do movimento é sempre a da transação.** A janela «Tratar» copia-a
   e não há forma de a mudar. O extracto do banco costuma ter a data de
   liquidação: uma venda feita a 30 de dezembro e liquidada a 2 de janeiro cai
   no ano errado.
6. **Comissões antigas.** Os movimentos gravados com comissão 0 trazem a
   comissão dentro do valor. Isto só afecta a divisão entre valor e despesas,
   não o ganho.

## 3. A proposta

### 3.1 Os campos fiscais

Uma migração numerada, como a da `coluna_imposto`, acrescenta:

- **`tipos_ativo.classificacao_fiscal`** (decisão 2), com um de três valores:
  - **Valores mobiliários:** ações, ETF, obrigações, fundos;
  - **Criptoativos;**
  - **Fora do IRS:** o ouro, os certificados de aforro, os bens, e por omissão
    os tipos novos.

  A migração classifica os tipos com os nomes que a aplicação cria no primeiro
  uso: ETF, Ações e Obrigações como valores mobiliários, Crypto como
  criptoativos. Os restantes ficam fora do IRS até se escolher. Os tipos
  criados no primeiro uso já vêm classificados.
- **`ativos.pais` e `contas.pais`** (decisão 3), com o código do país em ISO
  3166 (`PT`, `DE`, `NL`…), Portugal por omissão. O país do ativo serve as
  vendas e os dividendos; o da conta, os juros. Se o anexo J usar uma tabela
  de códigos própria (secção 5), a conversão faz-se no relatório.
- **`subcategorias.juros_irs`** (decisão 12), uma marca como a de «trata
  património», só nas subcategorias de receita (decisão 15). As transações das
  subcategorias marcadas contam como juros. As
  categorias do primeiro uso ganham, em Receita, uma subcategoria «Juros» já
  marcada.

Os campos escolhem-se nas páginas que já existem: a classificação em Tipos de
ativo, o país do ativo na edição do ativo, o país da conta em Contas, e a marca
de juros em Categorias.

### 3.2 As linhas de venda

- **O FIFO passa a ter um só sítio.** O percurso dos lotes sai do
  `_resumo_valor_ativo` para uma função partilhada, que devolve também, para
  cada venda, os lotes que consumiu.
  - O resumo e o património continuam a usá-la e não mudam: os testes de
    caracterização do FIFO têm de passar sem tocar em nenhum.
  - É o primeiro commit, sozinho (`refactor`).
- **Cada venda dá uma linha por lote consumido**, juntando os lotes comprados
  no mesmo dia (decisão 4). Cada linha tem:
  - a data da venda e o valor de realização. É a parte do valor bruto da venda
    (o total mais a comissão) que cabe às unidades da linha;
  - a data do lote e o valor de aquisição. É a parte do valor bruto das
    compras (o total menos a comissão) que cabe às unidades da linha;
  - as despesas e encargos: a parte das comissões da compra e da venda que
    cabe às unidades da linha (decisão 5);
  - os dias de detenção e o ganho da linha;
  - o ativo, o anexo e o país.
- **Arredondamentos.** As contas fazem-se em `Decimal` e cada linha arredonda
  ao cêntimo. Os totais somam as linhas já arredondadas, como se declaram.
- **Invariante, testada:** a soma dos ganhos das linhas de um ativo dá o ganho
  realizado do resumo, a menos dos cêntimos do arredondamento por linha.
- **Agrupamento.** As linhas agrupam-se por anexo (G se o país do ativo for
  Portugal, J se não), por país e por classificação. Os criptoativos
  separam-se também pela detenção, menos de 365 dias ou 365 ou mais (a
  confirmar, secção 5).

### 3.3 Os dividendos e os juros

- **Dividendos:** os movimentos `dividendo` do ano, por ativo, com a data, o
  valor recebido e o país do ativo (decisão 6: só o valor recebido).
- **Juros:** as transações do ano nas subcategorias marcadas, por conta, com a
  data, o valor recebido e o país da conta (decisão 13: só o valor recebido).
- **Agrupamento** (decisão 14). Os do estrangeiro agrupam-se por país, para o
  anexo J. Os portugueses ficam num grupo à parte, com a nota «retidos na fonte
  em Portugal: só se declaram se optares por juntá-los aos outros
  rendimentos» (a confirmar, secção 5).

### 3.4 Compras antigas e a data da operação

- **«Registar compra antiga», na página Ativos** (decisão 7). Abre uma compra
  sem transação, com data, quantidade, total e comissão, marcada como «antiga»
  na lista de movimentos.
  - Entra no FIFO, no valor do ativo e no relatório.
  - Não mexe na liquidez nem nas estatísticas, porque não há transação.
  - Só para compras: as vendas e os dividendos continuam a nascer das
    transações.
  - O backend já aceita um movimento sem `transacao_id`. O que é novo é a
    marca de antiga, que é a falta de transação, e o formulário.
- **A data da operação** (decisão 8).
  - Na janela «Tratar», a data vem preenchida com a da transação e pode
    mudar-se.
  - Depois, corrige-se na lista de movimentos do ativo, com um endpoint novo
    que muda a `data` do movimento e volta a verificar que nenhuma venda
    excede as unidades em carteira.
  - Não há migração: a coluna já existe.

### 3.5 A página IRS

- **Uma entrada nova, «IRS», no grupo Exportar** da barra lateral, ao lado do
  Retrato em PDF.
- **Escolhe-se o ano.** Os anos disponíveis são os que têm vendas, dividendos
  ou juros.
- **Secções:** as vendas, os dividendos e os juros, cada uma com a tabela
  pelos grupos de 3.2 e 3.3, as colunas pela ordem do quadro, e os totais
  (realização, aquisição, despesas e o saldo de ganhos e perdas, nas vendas).
- **Um botão «Exportar CSV» por tabela** (decisão 10), com as mesmas colunas e
  a vírgula decimal, para abrir no Excel. O CSV gera-se no backend
  (`GET /irs/{ano}/csv?tabela=…`) e não no browser: o frontend não tem testes,
  e assim o conteúdo do ficheiro fica coberto pelos testes do backend.
- **O aviso** (decisão 11). Se o ano escolhido tiver transações por tratar
  como ativo, a página diz quantas são, com um botão para os Ativos: uma venda
  ou um dividendo por tratar é uma linha que falta.
- **O backend:** `servicos/irs_serv.py`, com o relatório de um ano, e o
  endpoint `GET /irs/{ano}`, num router novo.

## 4. Decisões tomadas (14/11/2026)

1. **Âmbito:** as mais-valias de valores mobiliários e de criptoativos, os
   dividendos e os juros (depósitos, contas remuneradas, juros da corretora).
   As mais-valias imobiliárias e as despesas dedutíveis do e-Fatura ficam de
   fora.
2. **A classificação fiscal fica no tipo de ativo.** Um ativo que não encaixe
   no seu tipo (um ETC de ouro, por exemplo) leva um tipo próprio.
3. **O país fica em cada ativo, para as vendas e os dividendos, e em cada
   conta, para os juros**, com Portugal por omissão. A conta não serve para as
   vendas, porque a compra sai muitas vezes da conta do banco e não de uma
   conta da corretora.
4. **Uma linha por lote, juntando os lotes comprados no mesmo dia.** O valor
   de realização de cada linha é a parte do total da venda que cabe às suas
   unidades.
5. **As comissões vão para a coluna das despesas e encargos**, separadas dos
   valores brutos. Os movimentos antigos com comissão 0 ficam com ela dentro
   dos valores. Se o quadro do ano não tiver coluna de despesas, as comissões
   passam para dentro dos valores, sem mudar o ganho.
6. **Dividendos: só o valor recebido.** O bruto e o imposto retido tiram-se do
   relatório anual da corretora.
7. **«Registar compra antiga» na página Ativos**, só para compras.
8. **A data do movimento pode escolher-se** na janela «Tratar» e corrigir-se
   depois. O FIFO, o valor do ativo, o património e o relatório usam essa data.
9. **O imposto não se calcula.** Calcula-o o simulador do Portal das Finanças.
10. **Um botão «Exportar CSV»**, com as colunas pela ordem do quadro. Se o
    Portal aceitar importar um ficheiro (secção 5), o CSV segue esse formato.
11. **A página IRS avisa das transações por tratar como ativo** no ano
    escolhido. É uma excepção à regra de avisar só nas Transações: aqui, uma
    transação por tratar é uma linha que falta na declaração.
12. **Os juros identificam-se por uma marca «Juros (IRS)» na subcategoria.**
13. **Juros: só o valor recebido**, como nos dividendos.
14. **Os juros e os dividendos portugueses mostram-se à parte**, com a nota de
    que só se declaram se se optar por juntá-los aos outros rendimentos.
15. **A marca «Juros (IRS)» só existe nas subcategorias de receita**, como a
    classificação das despesas só existe nas de despesa. Uma marca noutro tipo
    é recusada, e perde-se se a categoria deixar de ser de receita.

## 5. A confirmar antes do passo 6

São regras da lei e do Modelo 3 que conheço só em termos gerais. Têm de se
confirmar nas instruções oficiais do ano a declarar (Portal das Finanças), e
cada confirmação fica registada neste plano com a fonte.

1. As colunas exactas dos quadros das vendas de valores mobiliários nos anexos
   G e J, e dos dividendos e juros no anexo J. Inclui:
   - os códigos de cada tipo de título e de rendimento;
   - o «país da fonte» e o «país da contraparte»;
   - se as despesas são uma coluna à parte;
   - a tabela de códigos de países.
2. Que o FIFO é a regra para identificar as unidades vendidas.
3. O tratamento dos criptoativos conforme o tempo de detenção (menos de 365
   dias, ou 365 ou mais):
   - em que anexo e quadro se declaram;
   - se os de 365 dias ou mais também se declaram.
4. Que o país do anexo J é o da corretora ou do banco, e não o do emitente do
   título.
5. Que os juros e os dividendos pagos em Portugal, com retenção na fonte, só se
   declaram (anexo E) se se optar pelo englobamento.
6. Que a data de realização é a da operação, e não a da liquidação.
7. Se o Portal das Finanças aceita importar as linhas de um ficheiro, e em que
   formato.

## 6. Passos e commits

Um commit por passo, com o lint, o ruff, o pyright e os testes a passar antes de
cada um. Cada passo de backend traz os seus testes no mesmo commit; os passos de
frontend verificam-se no browser (secção 7).

1. `refactor`: o percurso FIFO numa função partilhada, que também devolve os
   lotes de cada venda.
   - Os testes de `test_patrimonio_fifo.py`, `test_api_patrimonio.py` e
     `test_crescimento_patrimonio.py` passam **sem nenhuma alteração**.
   - Testes novos da função partilhada:
     - uma venda dentro de um só lote devolve esse lote, com as unidades e o
       custo proporcional;
     - uma venda que atravessa dois lotes devolve os dois, com as unidades de
       cada um;
     - duas vendas seguidas consomem os lotes pela ordem, e a segunda começa
       onde a primeira parou;
     - os custos dos lotes consumidos somam o custo vendido que dá o ganho
       realizado.
2. `feat`: os campos fiscais no modelo, com a migração, os schemas, a API e o
   primeiro uso.
   - **Migração** (`test_acrescentar_campos_fiscais.py`, numa base de dados
     antiga, como `test_acrescentar_coluna_imposto.py`):
     - os tipos ETF, Ações e Obrigações ficam valores mobiliários, Crypto fica
       criptoativo, e os outros ficam fora do IRS;
     - os ativos e as contas ficam com `PT`;
     - nenhuma subcategoria fica marcada como juros;
     - correr duas vezes não muda nada e devolve que não mudou;
     - os ids e as chaves estrangeiras ficam iguais.
   - **Backups:** restaurar um backup de antes da migração leva os campos
     novos (`test_backups/test_importar.py`).
   - **API:**
     - um país que não seja um código de duas letras é recusado, e um em
       minúsculas guarda-se em maiúsculas;
     - uma classificação fiscal desconhecida é recusada;
     - a marca de juros numa subcategoria que não é de receita é recusada;
     - mudar o tipo de uma categoria de receita para outro tira a marca às
       suas subcategorias.
   - **Primeiro uso:** os tipos criados vêm classificados, e a subcategoria
     Receita > Juros vem marcada.
3. `feat`: os campos fiscais nas páginas Tipos de ativo, Ativos, Contas e
   Categorias. Verificação no browser.
4. `feat`: «Registar compra antiga» na página Ativos.
   - Uma compra antiga (sem transação) entra no valor do ativo e no FIFO, e o
     saldo das contas e a liquidez do património não mudam.
   - Uma venda que antes era recusada por falta de unidades passa a ser aceite
     depois da compra antiga.
   - Uma compra antiga com data futura, quantidade zero ou negativa, ou total
     zero é recusada.
   - Uma venda ou um dividendo sem transação são recusados: só as compras
     podem ser antigas.
   - Apagar uma compra antiga de que uma venda precisa é recusado, como
     qualquer compra.
5. `feat`: a data do movimento na janela «Tratar» e o endpoint para a
   corrigir.
   - Criar um movimento com uma data diferente da transação guarda a data do
     movimento, e o resumo do ativo e a evolução do património usam-na.
   - Mudar a data de uma compra para depois da venda que a consome é recusado,
     e a base de dados fica como estava.
   - Mudar a data de uma venda para antes da compra que consome é recusado da
     mesma forma.
   - Uma data futura é recusada.
6. `feat`: o `irs_serv.py` e o endpoint `GET /irs/{ano}` (ver os casos em 7).
7. `feat`: a página IRS e o CSV.
   - **Backend** (`GET /irs/{ano}/csv`):
     - o cabeçalho tem as colunas pela ordem do quadro;
     - os valores levam vírgula decimal e as datas o formato do quadro;
     - um ano sem nada dá um ficheiro só com o cabeçalho;
     - uma tabela desconhecida dá 404.
   - **Frontend:** verificação no browser.
8. `docs`: o `docs/decisoes.md`, o `docs/modelo-dados.md`, a página Conceitos e
   o README.

## 7. Testes e verificação

**Regras para todos os testes:**
- Os valores esperados são calculados à mão e escritos como constantes, com a
  conta em comentário. Nunca se corre a função para colar o resultado.
- Usam os enums reais (`TipoMovimento`, `TipoCategoria` e a nova classificação
  fiscal), nunca texto.
- As datas são fixas: nenhum teste depende da data de hoje.
- Um comportamento questionável encontrado ao testar fica fixado como está e
  é-te reportado; não se corrige no mesmo passo.

**O relatório do ano (passo 6),** num ficheiro novo `test_api_irs.py`:
- **As linhas de venda:**
  - uma venda que consome dois lotes de datas diferentes dá duas linhas, com
    os valores brutos e as comissões repartidos pelas unidades;
  - dois lotes do mesmo dia dão uma só linha, com as unidades e os valores
    somados;
  - o exemplo das 18 VWCE, feito à mão:
    - 10 unidades compradas a 10/03/2023 por 1 000 € (+1 € de comissão);
    - 5 unidades a 15/06/2023 por 550 € e outras 5 no mesmo dia por 560 €
      (+1 € de comissão cada);
    - venda das 18 a 20/05/2025 por 2 340 € (−1 € de comissão);
    - resultado esperado em duas linhas:
      - 10 unidades: aquisição 1 000,00 €, realização 1 300,00 €
        (10/18 de 2 340 €), despesas 1,56 € (a comissão da 1.ª compra, 1 €, e
        10/18 da comissão da venda, 0,5556 €);
      - 8 unidades: aquisição 886,00 € (550 € e 3/5 de 560 €), realização
        1 040,00 € (8/18 de 2 340 €), despesas 2,04 € (1 € da 2.ª compra,
        3/5 de 1 € da 3.ª, e 8/18 da comissão da venda, 0,4444 €);
      - as despesas somam 3,60 €: as comissões das unidades vendidas;
  - um movimento antigo com comissão 0 fica com os valores como estão e
    despesas 0;
  - uma venda a 31/12 e outra a 01/01 caem em anos diferentes, pela data do
    movimento e não pela da transação;
  - um criptoativo detido 364 dias e outro 365 ficam em grupos diferentes;
  - um ativo de um tipo «fora do IRS» não aparece;
  - um ativo com país `DE` vai para o anexo J, no grupo da Alemanha, e um com
    `PT` para o anexo G;
  - os totais somam as linhas já arredondadas, ao cêntimo;
  - um bem sem unidades vendido não aparece (é «fora do IRS»).
- **A invariante:** para vários ativos com compras, vendas parciais e
  comissões, a soma dos ganhos das linhas bate com o realizado do resumo do
  ativo, a menos de um cêntimo por linha.
- **Os dividendos:**
  - só os do ano, com o valor recebido e o país do ativo;
  - os de um ativo com país `PT` ficam no grupo à parte.
- **Os juros:**
  - só as transações das subcategorias marcadas, e só as do ano;
  - o país vem da conta da transação;
  - uma transação da mesma categoria, mas de uma subcategoria sem marca, não
    entra;
  - os de uma conta `PT` ficam no grupo à parte.
- **O aviso:** conta só as transações por tratar como ativo com data no ano
  escolhido.
- **Os anos disponíveis:** só os que têm vendas, dividendos ou juros.

**Mutação:** os testes novos de cada passo de backend são verificados por
mutação numa cópia do backend, como diz o AGENTS.md. Os resultados são
reportados todos, e um mutante equivalente é reportado, não «corrigido».

**Frontend:** o `npm run lint`, e cada página verificada no browser contra o
backend de teste, com a base de demonstração, nos dois temas:
- os campos novos em Tipos de ativo, Ativos, Contas e Categorias gravam e
  voltam a aparecer depois de recarregar;
- «Registar compra antiga» cria o movimento e o valor do ativo muda;
- a data na janela «Tratar» e a correcção na lista de movimentos;
- a página IRS com um ano com vendas, dividendos e juros, o aviso, e o CSV
  descarregado e aberto.

**Dados reais:** a tua base não está neste ambiente. Depois de juntares as
alterações, os totais do ano devem bater com os documentos anuais da corretora
e do banco. Uma diferença ou é um movimento em falta, ou um ponto da secção 5 a
rever.

## 8. Fora do âmbito

Ficam para depois, se os quiseres:
- as mais-valias imobiliárias (anexo G, com os coeficientes de desvalorização e
  o reinvestimento);
- o imposto retido nos dividendos e nos juros (decisões 6 e 13);
- os desdobramentos de ações (splits);
- as transferências de títulos entre corretoras;
- as deduções do e-Fatura;
- a simulação do imposto.
