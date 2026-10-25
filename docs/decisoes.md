# Decisões de design

As convenções da aplicação: como se conta cada coisa e porquê. Uma decisão daqui não se reverte sem a discutir.

## Categorias e regras

Cada categoria tem um `tipo`, que decide o seu papel nas estatísticas:

| Tipo | Papel nas estatísticas |
|---|---|
| `despesa` | Incluída nos totais de despesa e nas médias por categoria |
| `receita` | Incluída nos totais de receita e no cálculo da taxa de poupança |
| `investimento` | Tratada à parte, não distorce despesa nem receita |
| `transferencia` | Excluída de todas as métricas (movimentos internos entre contas) |

- Reembolsos são tratados como redução de despesa, não como receita: um reembolso regista-se na categoria de despesa a que diz respeito, e o valor positivo reduz a despesa. Não há marca de reembolso; o tipo da categoria e o sinal decidem tudo, da mesma forma em todos os ecrãs
- Os nomes de categorias, e os de subcategorias dentro da mesma categoria, não se repetem nem ficam vazios. Para comparar, ignoram-se as maiúsculas e os acentos: «Salário», «salário» e «salario» são o mesmo nome
- Uma categoria com transações não se pode apagar (é preciso mudá-las de categoria primeiro); sem transações, apaga-se com as suas subcategorias e regras. Apagar uma subcategoria deixa as suas transações por categorizar na mesma categoria, e as regras que apontavam para ela ficam sem subcategoria
- Quando várias regras casam com a mesma descrição, ganha a de palavra-chave mais longa (a mais específica) e, em empate, a mais antiga; essa primeira regra decide sozinha a categoria e a subcategoria, mesmo que deixe a subcategoria por preencher
- Uma regra sem categoria é uma exclusão: «nunca atribuir categoria» às transações que casam com ela, para as rever à mão sem forçar uma categoria errada. Uma exclusão ganha sempre, seja qual for o comprimento: uma exclusão «MB» deixa por categorizar uma descrição que também case com «MB WAY SALARIO». Para não bloquear uma regra, a exclusão tem de ser mais específica

## Contas e saldo

- Uma conta com transações não se pode apagar, só desactivar. Desactivar esconde-a das listas de contas, mas a conta continua a contar no património e na sua evolução; na página Património aparece, marcada como inactiva, enquanto o saldo não for zero
- O saldo de referência de uma conta é o saldo no fim da data de referência, que pode ser qualquer dia. O saldo noutro dia calcula-se a partir dele: para a frente somam-se as transações seguintes, para trás tiram-se as que ainda não tinham acontecido
- O saldo calculado compara-se com o campo `saldo` das transações: o do extracto ou, nas contas sem nenhum perfil de importação com saldo, um saldo escrito à mão de vez em quando (só nessas se escreve, muda ou apaga). O saldo de referência também conta; se o extracto tiver saldo nesse dia, vale o do extracto, e uma diferença aí corrige-se no saldo de referência. Não há tabela própria para os saldos verificados
- A comparação é ao fim de cada dia, porque a ordem das transações dentro do dia não fica guardada. Num dia com vários saldos do extracto, o do fim do dia é o que não é o saldo antes (saldo − valor) de nenhuma outra transação. Se isso não chegar (uma transação de 0 €, um saldo repetido), usa-se o mais próximo do esperado, e o dia fica marcado como de ordem incerta. O esperado é o saldo do banco no ponto anterior mais os movimentos desde então, ou o calculado se o saldo de referência ficar pelo meio ou não houver ponto anterior: comparar sempre com o calculado inventava diferenças quando já havia uma de trás
- A verificação não tem botão: corre ao abrir a página Transações (para todas as contas activas, com a linha do resumo só nas que têm diferenças) e depois de importar, de criar ou apagar uma transação manual e de escrever um saldo, com um pop-up se houver diferenças. Mostra a diferença actual e os intervalos entre dois saldos seguidos em que mudou; antes do primeiro saldo não se sabe nada. Se o último saldo tiver mais de 31 dias antes da última transação da conta, sugere escrever um novo. Uma diferença não se ignora: corrige-se com uma transação manual, que fica registada
- As transações criadas à mão servem só para corrigir o saldo. Ficam marcadas como manuais e são as únicas que se podem apagar; uma ligada a um movimento de ativo só se apaga depois do movimento. Sem categoria nem subcategoria escolhidas, aplicam-se as regras, como na importação. Se um extracto importado depois trouxer a mesma transação, só é dada como duplicada se tiver a mesma data, descrição e valor (e, num perfil com saldo, o mesmo saldo); se não, fica duas vezes e a manual apaga-se à mão

## Importação

- O separador dos CSV (vírgula, ponto e vírgula ou tabulação) é detetado automaticamente
- Uma importação é tudo ou nada: basta uma linha com erro (data inválida, valor que não bate com o separador decimal do perfil, linha de totais no fim do extracto) para o ficheiro inteiro ser recusado, e a pré-visualização mostra todas as linhas com erro
- Uma linha igual a outra já existente na conta (mesma data, descrição, valor e saldo) é duplicada, mas conta-se quantas cópias há: entram as linhas iguais que o extracto traz a mais do que a conta já tem (dois cafés iguais no mesmo dia, um deles só no extracto seguinte). Num perfil sem saldo, o saldo não entra na comparação, porque o da conta é o que se escreveu à mão
- Só se desfaz a importação mais recente de cada conta: uma anterior pode ter linhas que as seguintes deram como duplicadas, e desfazê-la apagava-as. Uma importação feita para a conta errada desfaz-se depois de desfeitas as que vieram a seguir nessa conta. Desfazer apaga as transações que a importação trouxe, com as categorias, subcategorias e notas que entretanto ganharam, e a importação sai do histórico. Se alguma dessas transações já foi tratada como ativo, a aplicação mostra os movimentos e pergunta se os apaga também; sem essa confirmação, não apaga nada. Os preços que os movimentos gravaram ficam, e se apagar uma compra deixar uma venda com mais unidades do que as que havia nessa data, nada é apagado
- Um perfil de importação tem sempre uma conta: as transações sem conta contariam nas estatísticas mas nunca na liquidez. Por isso, uma conta sem transações não se pode apagar enquanto um perfil a usar (é preciso apagar o perfil primeiro), e um perfil que tenha ficado sem conta deixa de poder importar
- A coluna de comissão de um perfil é sempre tratada como um pagamento: entra com sinal negativo, venha positiva ou negativa no extracto
- No modo de duas colunas, o débito sai sempre e o crédito entra sempre, venha o sinal que vier no extracto: o valor é `|crédito| − |débito|`, porque há bancos que escrevem o débito com sinal menos

## Estatísticas

- As médias, as medianas e as taxas contam todos os meses completos com transações, mesmo os que só têm transferências ou transações por categorizar; pressupõe-se que as transações importadas são categorizadas logo a seguir. O mês em curso fica de fora, porque está incompleto: não entra nos cartões, na tabela por categoria nem nas médias de 3 e de 12 meses da taxa de poupança, mas conta nos totais e nas somas do período, nas barras do gráfico mensal e no Histórico. Um mês passado com o extracto incompleto conta como inteiro e puxa as médias para baixo, tanto mais quanto menos meses tiver o período: a aplicação não tenta adivinhar se um mês está completo. Sem nenhum mês completo no período, as médias mostram «—»
- Cada subcategoria de despesa pode ter uma classificação, uma só: **Essencial** (precisa-se e repete-se: supermercado, renda, combustível, seguro), **Evitável** (dispensável e repete-se: restauração, jogos, viagens) ou **Extraordinária** (compra isolada que não se espera repetir nos próximos dois ou três anos: o carro, o PC). Sem classificação, conta como as outras. A classificação é da subcategoria e vale para todas as suas transações: para separar uma compra grande das pequenas, cria-se outra subcategoria (por exemplo, «PC» à parte de «Hardware»). Só as categorias de despesa têm classificação; quando uma categoria deixa de ser de despesa, as suas subcategorias perdem-na
- As despesas anuais (o seguro, o IUC, a inspeção) não são extraordinárias: contam na média, repartidas pelos meses
- O mês típico é a média mensal da despesa sem as extraordinárias, sobre os mesmos meses que as outras médias. As extraordinárias nunca desaparecem: mostram-se sempre à parte, com a lista e o total do período, e um reembolso numa subcategoria extraordinária reduz esse total. A divisão entre essencial e evitável mostra quanto da despesa se podia cortar
- O gráfico da taxa de poupança inclui as extraordinárias, com uma opção para as tirar. A sua escala começa nos 0 %: uma taxa negativa (gastou-se mais do que se recebeu) fica de fora, com um aviso e um botão para a incluir, para que um mês com uma compra grande não esmague o resto da linha

## Património e ativos

As transações das subcategorias marcadas com o indicador de património alimentam o módulo de Património. Cada ativo é classificado como:

| Classificação | Papel |
|---|---|
| Investimento | Património com retorno expectável (ex. ETFs, ações, cripto): conta para o cartão de Investimentos |
| Bem | Património sem retorno expectável (ex. imóvel, viatura): conta apenas para o total de património |

- Um bem sem unidades (ex. imóvel, viatura) vende-se sempre por inteiro: qualquer venda desconta o custo acumulado todo e o bem deixa de contar para o património. Para vender partes de um bem, regista-se o bem com unidades (ex. 100 unidades = 100%), e as vendas parciais passam pelo FIFO
- O crescimento do património por mês é a inclinação da recta dos mínimos quadrados ajustada ao património no fim de cada mês, e não (último − primeiro) ÷ meses: um mês fora do normal pesa pouco e os saltos de preço ficam repartidos. Separa-se em **valorização** (o ganho acumulado dos ativos: valor − custo + realizado em vendas e dividendos registados como movimento) e **do que poupas** (o resto); as duas parcelas somam o total ao cêntimo. Comprar um ativo não muda nenhuma das duas, e um bem só entra pela desvalorização. O período acompanha o filtro de ano, deixa de fora o mês em curso e precisa de pelo menos 3 meses completos

## Retrato em PDF

- O retrato descreve os últimos 12 meses completos (ou menos, se o histórico for mais curto), com as médias contadas como nas Estatísticas: o mês normal é a média, e não a mediana, sem as extraordinárias, que se somam à parte no período. O investimento não aparece no mês normal, mas no património, como o total investido no período: num ano em que se investe dinheiro que já estava na conta, investe-se mais do que fica, e os dois números lado a lado pareciam contraditórios
- A projeção soma ao património de hoje, todos os meses, a parte do crescimento que vem da poupança (sem a valorização, que num bom ano se prolongaria para sempre). Com 0 % é só isso; nos cenários de 4 % e 7 % ao ano, os investimentos rendem essa taxa, composta todos os meses, e recebem por mês a média do que se investiu no período. São cenários, não previsões: o rendimento não é garantido

## Valores e dados

- Os valores em euros arredondam ao cêntimo com a metade para longe de zero, como o ARRED do Excel: 2,345 dá 2,35 e -2,345 dá -2,35. Quantidades e preços guardam a precisão com que foram introduzidos, e valores não numéricos (NaN, infinito) são recusados
- Antes de cada restauro de um backup, guarda-se uma cópia de segurança automática da base de dados actual. Ficam as 5 mais recentes, em `dados/`, com a data e a hora no nome
