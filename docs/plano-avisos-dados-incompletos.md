# Plano: avisar quando os números assentam em dados incompletos

Estado: **executado** (passos 1 a 4). Falta confirmar os avisos com os dados
reais (secção 5).

Pequenas decisões tomadas durante a execução:

- Os pares de transferências formam-se do mais próximo no tempo para o mais
  afastado, e em empate pelo que começa mais cedo, em vez de se percorrerem por
  data. Assim, duas saídas de 100 € e uma entrada de 100 € deixam sem par a
  saída mais afastada da entrada, e não a mais antiga.
- O endpoint das transferências sem par devolve, em vez de um total, as somas
  das entradas e das saídas, como o das transações por categorizar. Os dois
  avisos descrevem os valores da mesma maneira.

## 1. O problema

Há três situações em que a aplicação mostra números certos para os dados que tem,
mas os dados estão incompletos, e nenhum ecrã o diz:

1. **Transações por categorizar.** Uma transação sem categoria fica fora de
   todas as estatísticas (`join` com `categorias` em `estatisticas.py`). Uma
   sem subcategoria conta nos totais, mas cai em «Sem subcategoria» e «Sem
   classificação», e nunca nas extraordinárias. O único sinal é o contador na
   barra lateral, que não diz o que lhes acontece. Um mês com 30 transações
   por tratar parece um mês poupado. O `docs/decisoes.md` pressupõe que «as
   transações importadas são categorizadas logo a seguir»; o aviso é a rede
   para quando isso não acontece, e não muda a decisão.
2. **Transações por tratar como ativo.** Uma compra de ETF numa subcategoria
   com «trata património», ainda sem movimento, já saiu da liquidez mas não
   entrou nos investimentos, e o património fica errado nesse valor até ser
   tratada. **Este plano não lhe acrescenta avisos** (decisão 4): o contador da
   barra lateral, junto aos Ativos, continua a ser o único sinal.
3. **Transferências sem par.** As transferências ficam fora das métricas porque
   se pressupõe que são movimentos entre contas próprias, com uma saída numa
   conta e a entrada noutra. Se a outra conta não está na aplicação, ou se a
   outra metade foi mal categorizada, o dinheiro desaparece do património sem
   aparecer como despesa. Nada verifica que cada saída tem a sua entrada.

Fora do âmbito deste plano (ficam para depois, se os quiseres):
- a desvalorização automática dos bens;
- conferir o total de um movimento com o valor da transação;
- a categoria em que fica um dividendo.

## 2. A proposta

Os avisos ficam **só na página Transações**, que é onde se resolvem (decisão
4). Aparecem ao abrir a página, por baixo do resumo da verificação do saldo, com
o estilo `.aviso` que já existe, e só quando há alguma coisa a dizer.

### 2.1 Transações por categorizar

**Backend.** O `GET /transacoes/por-categorizar/total`, que já dá o número ao
contador da barra lateral, passa a trazer também:
- `entradas`: a soma das transações positivas, em euros;
- `saidas`: a soma das negativas, em euros.

O campo `total` fica como está, para o contador não mudar. A definição também
não muda: sem categoria **ou** sem subcategoria (decisão 1).

**Transações.** O aviso:

> 12 transações por categorizar (−340,00 € a sair, +50,00 € a entrar): ficam
> fora das estatísticas, ou da sua divisão, até serem categorizadas.
> [Mostrar]

O botão liga o filtro «Por categorizar» da própria página, o mesmo que o botão
dos filtros já liga. O aviso é actualizado quando se categoriza uma transação,
tal como o contador da barra lateral.

### 2.2 Transferências sem par

**Backend.** Um serviço novo, `servicos/transferencias.py`, com
`transferencias_sem_par(db)`, e o endpoint `GET /transacoes/transferencias-sem-par`.
Uma transferência tem par quando há outra transferência que cumpre tudo isto:
- está noutra conta;
- tem o valor simétrico, ao cêntimo;
- tem uma data a 7 dias desta, no máximo (decisão 2).

O emparelhamento é feito um a um: duas saídas de 100 € e uma entrada de 100 €
deixam uma saída sem par. Percorre-se por data e escolhe-se o par mais próximo
no tempo, para ser determinístico. O endpoint devolve a lista das que ficam sem
par, com data, conta, descrição e valor, e o total.

**Transações.** O aviso:

> 3 transferências sem par (−1 500,00 €): o dinheiro saiu ou entrou sem passar
> por outra conta registada, e não conta como despesa nem como receita.
> [Ver a lista]

«Ver a lista» abre a lista das transferências sem par: data, conta, descrição
e valor. O aviso não se pode dar como visto (decisão 3). Para o resolver, ou se
acrescenta a conta que falta e se importa o seu extracto, ou se muda a categoria
da transação (por exemplo, para uma despesa, se era um pagamento a outra
pessoa), como se faz com as diferenças de saldo. O aviso é actualizado quando se
muda a categoria de uma transação.

### 2.3 Documentação

- Em `docs/decisoes.md`, um parágrafo nas Estatísticas (transações por
  categorizar) e outro em Contas e saldo (transferências sem par), com o que se
  considera incompleto. Fica escrito também que os avisos ficam só nas
  Transações.
- Na página Conceitos, na explicação das transferências, uma frase a dizer que
  cada transferência deve ter a outra metade numa conta registada.

## 3. Decisões tomadas (28/10/2026)

1. **Por categorizar** é sem categoria **ou** sem subcategoria, a mesma
   definição do contador e do filtro das Transações.
2. **Duas transferências emparelham a 7 dias, no máximo.**
3. **Uma transferência sem par não se dá como vista.** Resolve-se registando a
   conta em falta ou mudando a categoria, como as diferenças de saldo. Não há
   marca nem mudança no esquema.
4. **Os avisos ficam só nas Transações.** As Estatísticas, o Histórico, o
   Património e o retrato em PDF ficam como estão, sem avisos.

## 4. Passos e commits

Um commit por passo, com o lint, o ruff, o pyright e os testes a passar antes de
cada um.

1. `feat`: as entradas e as saídas no `por-categorizar/total`, com os testes, e
   o aviso das transações por categorizar nas Transações.
2. `feat`: `transferencias_sem_par` e o endpoint, com os testes.
3. `feat`: o aviso das transferências sem par nas Transações.
4. `docs`: `docs/decisoes.md` e a página Conceitos.

## 5. Testes e verificação

Os valores esperados são calculados à mão, com a conta em comentário, e usam os
enums reais.

- **`por-categorizar/total`:**
  - uma transação sem categoria e outra sem subcategoria, que contam as duas;
  - entradas e saídas separadas;
  - um reembolso por categorizar, que é uma entrada;
  - sem nenhuma por categorizar, tudo a zero.
- **Transferências sem par:**
  - um par no mesmo dia, em contas diferentes;
  - um par a 3 dias, com o fim do mês pelo meio;
  - um par exactamente a 7 dias, que ainda emparelha;
  - um par a 8 dias, que já fica sem par;
  - duas transferências na mesma conta, que nunca formam par;
  - valores que diferem 1 cêntimo;
  - duas saídas iguais para uma só entrada, que deixam uma sem par;
  - a escolha do par mais próximo, quando há dois candidatos.
- **Mutação:** os testes novos são verificados por mutação numa cópia em `/tmp`,
  como diz o AGENTS.md.
- **Frontend:** o `npm run lint` e uma verificação no browser.
  - O browser corre contra um backend de teste, com `RASTREIO_DB_DIR` a apontar
    para uma cópia da base de demonstração. Nos dados de demonstração junta-se
    uma transação por categorizar e uma transferência sem par.
  - Verifica-se cada aviso nos dois temas, que desaparecem quando se resolve o
    que os causa, e que as outras páginas e o PDF não mudaram.
- **Dados reais:** a base real não está neste ambiente. Depois de juntares as
  alterações, convém abrires a aplicação e confirmares se os avisos que
  aparecem fazem sentido. As transferências antigas sem par são as mais
  prováveis.
