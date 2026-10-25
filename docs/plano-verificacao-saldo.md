# Plano: verificar o saldo das contas e criar transações à mão

Estado: **executado** (passos 3.1 a 3.6). Falta a verificação com os dados
reais (secção 4), numa cópia da BD.

Pequenas decisões tomadas durante a execução:

- O saldo de referência da conta conta como um ponto de controlo, com
  diferença 0: o primeiro intervalo começa nele, e a sugestão dos 31 dias conta
  a partir dele numa conta sem saldos. Se o extracto tiver saldo no dia da
  referência, vale o do extracto.
- Uma transação manual ligada a um movimento de ativo não se apaga (409): o
  movimento apaga-se primeiro.
- Depois de fechado, o pop-up da verificação deixa uma linha com «Ver», para o
  abrir outra vez.

Correções depois da revisão do código:

- Os intervalos medem-se só entre dois pontos de controlo seguidos: antes do
  primeiro não se sabe qual era a diferença (havia um «até» inventado quando o
  primeiro saldo era anterior à referência). Uma diferença no dia da
  referência é do próprio saldo de referência, e o pop-up manda corrigi-lo na
  página Contas, em vez de propor uma transação.
- A decisão 14 aplica-se só aos perfis sem saldo: nos perfis com saldo, a
  deteção de duplicados compara os quatro campos, como antes.
- Os cêntimos arredondam com a metade para longe de zero, como `arredondar`.
- O mesmo saldo do fim do dia escrito em duas transações do dia já não marca o
  dia como de ordem incerta.
- Com o último saldo certo mas diferenças nos anteriores, o pop-up abre na
  mesma: falta ou sobra uma transação no passado.

Correções depois do teste com os dados reais (25/10/2026):

- Num dia de ordem incerta, o saldo do fim do dia escolhe-se pelo mais próximo
  do **esperado** (o saldo do banco no ponto anterior mais os movimentos desde
  então), e não do calculado. Com uma diferença de 10,10 € já de trás, o dia
  05/02/2026 do ActivoBank (+1,20 € e −1,20 €) dava −1,20 € e +1,20 €
  inventados.

## 1. O problema

O saldo de cada conta é calculado (`saldo_conta_em`, em
`servicos/patrimonio_serv.py`) a partir do saldo de referência e das
transações. Se faltar uma transação, ou houver uma a mais, o saldo fica errado
e nada o mostra. Exemplo: o ActivoBank está 10,10 € acima do banco, porque
falta a saída de 10 € de 11/06/2025 e há 0,10 € de diferença em 13/05/2025.

Também não há forma de acrescentar a transação que falta: só se importam
extractos.

## 2. Decisões tomadas (23/10/2026)

### Verificação

1. Os saldos esperados vêm **só** do campo `transacoes.saldo`, que já existe.
   - Nos bancos cujo extracto traz o saldo, vem da importação, como hoje.
   - Nos outros, o utilizador escreve-o de vez em quando (por exemplo, uma vez
     por mês) numa transação: o saldo da conta **no fim desse dia**. Não há
     tabela nova.
2. O saldo só se pode escrever, mudar ou apagar à mão nas contas que não têm
   nenhum perfil de importação com saldo (`tem_saldo`). Nas outras, o campo é
   do extracto e fica só de leitura.
3. Como a BD não guarda a ordem das transações dentro de um dia, a comparação
   faz-se **ao fim do dia**. Num dia com vários saldos, o do fim do dia
   descobre-se pelo próprio extracto: o saldo antes de cada transação é o seu
   saldo menos o seu valor, e a última do dia é aquela cujo saldo não é o
   «saldo antes» de nenhuma outra.

   | Transação | Valor | Saldo | Saldo antes |
   |---|---|---|---|
   | Café | −20 € | 980 € | 1 000 € |
   | Supermercado | −30 € | 950 € | 980 € |
   | Ordenado | +100 € | 1 050 € | 950 € |

   1 050 € não é o «saldo antes» de nenhuma, por isso é o do fim do dia.
   - Se não houver exactamente uma candidata (uma transação de 0 €, um saldo
     repetido no mesmo dia), usa-se a menor diferença entre o saldo calculado
     e os saldos do dia, e o resumo marca o dia como «ordem incerta».
   - Ao escrever um saldo num dia com mais do que uma transação, o ecrã avisa
     «indica o saldo da conta no fim deste dia».

   Rejeitadas: escolher sempre a menor diferença (engana quando o erro é
   parecido com os movimentos do dia, e pode dar o dia como certo por
   coincidência) e saltar os dias com vários saldos (perde pontos de controlo).

4. O resultado é **só um resumo**, num pop-up:
   - a diferença actual (no último dia com saldo);
   - **todos** os intervalos em que a diferença mudou, com o valor da mudança;
   - os dias com «ordem incerta» (decisão 3), se houver;
   - o botão «Criar transação de correção».

   ```
   Saldo calculado 10,10 € acima do banco.
   Entre 12/05 e 13/05/2025: +0,10 €
   Entre 10/06 e 12/06/2025: +10,00 €
   [Criar transação de correção]
   ```
5. A verificação corre **sozinha**, para a conta em causa, quando:
   - se importa um extracto (o resumo aparece no resultado da importação);
   - se cria ou apaga uma transação manual;
   - se escreve, muda ou apaga um saldo à mão.

   Não há botão para a correr. Para ver o estado actual de uma conta, escreve-se
   o saldo de hoje.
6. O pop-up só aparece quando há diferença. Se tudo bater certo, basta uma
   linha discreta («Saldo confirmado em 30/09/2026»).
7. Se a conta não tiver nenhum saldo, ou se o último for muito antigo, aparece
   uma pequena sugestão para o acrescentar. «Muito antigo» é mais de 31 dias
   antes da última transação da conta (e não antes de hoje, para não avisar só
   porque ainda não se importou o mês).
8. Não há «ignorar» uma diferença: uma diferença que não se queira investigar
   (por exemplo, um erro do banco) corrige-se com uma transação manual, que
   fica registada.

### Transações manuais

9. Coluna nova `transacoes.manual` (booleano). Nenhum campo existente serve:
   `importacao_id` a NULL também é o das transações importadas antes do
   histórico de importações.
10. Cria-se em dois sítios: um botão «Nova transação» na página Transações, e o
    botão do pop-up, com a data e o valor da correção já preenchidos. Ambos
    mostram um aviso claro de que inserir transações à mão não é recomendado
    (o normal é importar o extracto).
11. Campos: conta, data, descrição, valor, categoria e subcategoria
    (opcionais) e notas. Se não se escolher categoria nem subcategoria,
    aplicam-se as regras, como na importação.
12. Só as transações manuais se podem apagar. As importadas continuam a sair
    só ao desfazer a importação.
13. Duplicados: aceita-se o risco. Se se importar depois um extracto que traga
    a mesma transação, a manual apaga-se à mão (a verificação mostra a
    diferença).

### Importação

14. Num perfil **sem saldo**, a deteção de duplicados compara só a data, a
    descrição e o valor, sem olhar para o saldo da BD.
    Sem isto, escrever um saldo numa transação fazia-a voltar a entrar na
    importação seguinte de um extracto sobreposto. Os bancos com saldo ficam
    como hoje.

## 3. Passos (modelo → schema → router → api → página)

### 3.1 Modelo e migração (`backend/database.py`)

- `Transacao.manual`: booleano, NOT NULL, a falso nas existentes.
- Migração nova **no fim** de `MIGRACOES`, `acrescentar_transacao_manual`, ao
  estilo de `acrescentar_importacao_id`: `ALTER TABLE transacoes ADD COLUMN
  manual BOOLEAN NOT NULL DEFAULT 0`. Um `ADD COLUMN` com `DEFAULT` não reescreve
  a tabela. Para a BD nova bater certo com a migrada, o modelo leva
  `server_default` (confirmar o DDL que o SQLAlchemy gera). Idempotente.
- Teste `test_acrescentar_transacao_manual.py`, como o de `classe_despesa`.
- Correr numa **cópia** da BD real antes de tudo.

### 3.2 Importação (`backend/importador_transacoes.py`)

- Decisão 14: nos perfis sem saldo, a chave é (data, descrição, valor); nos
  perfis com saldo continua a ser a de quatro campos.

### 3.3 Verificação (`backend/servicos/` e `routers/contas.py`)

- Uma função de serviço que, para uma conta, percorre os dias com saldo por
  ordem, calcula o saldo ao fim de cada dia (numa só passagem, com a mesma
  regra de `saldo_conta_em`) e devolve:
  - `diferenca_atual` (calculado − banco, no último dia com saldo);
  - os `intervalos` em que a diferença mudou: `de`, `ate`, `variacao`;
  - a data do último saldo e se se deve sugerir um novo (decisão 7).
  - O saldo do fim de cada dia escolhe-se como na decisão 3, com a menor
    diferença e a marca «ordem incerta» só quando a ordem não se reconstrói.
- `GET /api/contas/{id}/verificacao-saldo`. O frontend chama-o nos momentos da
  decisão 5; não se mexe na resposta da importação.

### 3.4 Transações (`schemas.py`, `routers/transacoes.py`)

- `POST /api/transacoes/`: `TransacaoCreate`. Valida a conta, a categoria e a
  subcategoria como o `PUT`; `manual=True`; regras se não vier categoria nem
  subcategoria (decisão 11).
- `DELETE /api/transacoes/{id}`: só se `manual`, senão 409.
- `PUT`: aceitar `saldo` (com `model_fields_set`, para se poder apagar), só nas
  contas da decisão 2, senão 409.
- Listagem: acrescentar `manual` e `saldo_editavel` a cada linha.

### 3.5 Frontend

- `api/transacoes.js`: `criarTransacao`, `apagarTransacao`; `api/contas.js`:
  `verificarSaldo`.
- Um componente partilhado em `components/` para o resumo (pop-up), usado em
  Importação e Transações.
- `pages/Transacoes.jsx`: botão «Nova transação» com o aviso; etiqueta
  «manual» e botão de apagar nas manuais; o saldo editável nas linhas com
  `saldo_editavel`, com o aviso do fim do dia; o resumo depois de cada acção da
  decisão 5.
- `pages/Importacao.jsx`: o resumo no resultado da importação.
- `pages/Sobre.jsx`: explicar a verificação e as transações manuais.

### 3.6 Documentação

- `README.md`, «Decisões de design»: as decisões da secção 2.
- `docs/modelo-dados.md`: a coluna `manual` e o uso do `saldo`.

### 3.7 Testes

Valores calculados à mão, com a conta em comentário. Casos mínimos:

- importação: uma linha sem saldo é duplicada de uma transação com o mesmo
  dia, descrição e valor que tem saldo escrito à mão; uma linha com saldo
  continua a usar os quatro campos;
- verificação: tudo certo; uma transação em falta (um intervalo); dois erros
  (dois intervalos, como o ActivoBank); o exemplo da decisão 3 com uma entrada
  de 50 € em falta (a diferença é 50 €, não os 20 € da menor diferença) e com
  um erro de −70 € (não dá o dia como certo); dia com ordem incerta; saldos
  antes da data de referência; conta sem saldos; último saldo antigo, com 31 e
  32 dias; só a conta pedida;
- criar: com categoria; sem categoria (aplica regras); subcategoria de outra
  categoria (400); conta inexistente (404); fica `manual`;
- apagar: manual (apaga); importada (409);
- saldo: escrever, mudar e apagar numa conta sem perfil com saldo; recusar numa
  conta com perfil com saldo.

Verificar os testes novos por mutação numa cópia em `/tmp`.

## 4. Verificação com os dados reais (numa cópia)

No ActivoBank, a verificação deve mostrar uma diferença de +10,10 €, com
+0,10 € à volta de 13/05/2025 e +10,00 € à volta de 11/06/2025.

## 5. Fora do âmbito

- Guardar a ordem das transações dentro do dia (permitiria comparar
  transação a transação).
- Avisar na importação quando uma linha coincide com uma transação manual.
