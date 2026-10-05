"""Testes de caracterização de `aplicar_regras`, o motor de regras da importação.

Fixam o comportamento **actual** de `backend/importador_transacoes.py:5-23`, a
função que decide a categoria e a subcategoria de cada transação importada. A
função não toca na base de dados, não recebe `Session` e não faz flush, por isso
nenhum teste pede a fixture `session`: é um teste de função, àsemelhança de
`test_estatisticas_totais.py`.

Os objectos que entram são `SimpleNamespace` com os mesmos nomes de campo dos
modelos. Aqui não há nem `enum` nem comparação com constantes: a função só lê
`int`/`None` e `str` de `RegraCategorizacao`, e `int`/`None`/`str` de
`Transacao`. Se algum dia a função passar a tocar no `relationship` `categoria`
ou no `TipoCategoria`, este ficheiro deixa de chegar e tem de ser reescrito com
os modelos reais.

O que a função faz, em duas fases
---------------------------------

**Fase 1, exclusão (linhas 6-11).** Percorre as regras e salta as que têm
`categoria_id` definido (linhas 8-9). Para a primeira das restantes, se
`palavra_chave.upper()` estiver dentro de `descricao.upper()` (linha 10), faz
`return` e sai. A fase 1 corre sempre por inteiro antes da fase 2, pelo que uma
regra de exclusão ganha a qualquer regra de categorização, mesmo que venha
depois na lista.

Uma regra de exclusão não é um tipo: é só uma regra com `categoria_id is None`.
O `return` não escreve nada na transação.

**Fase 2, categorização (linhas 13-23).** Percorre as regras, salta as de
exclusão (linhas 15-16) e, na primeira cuja palavra-chave case, atribui em dois
casos e não noutros:

- `transacao.categoria_id is None` (linha 18) — escreve categoria **e**
  subcategoria, esta última pode ser `None`;
- `categoria_id == regra.categoria_id` **e** `subcategoria_id is None`
  (linha 21) — escreve só a subcategoria.

Nos restantes casos — já tem categoria **diferente**, ou já tem a mesma categoria
com subcategoria — não é atribuído nada e mesmo assim o `break` da linha 23
consome a regra: nenhuma posterior é avaliada.

Nada disto é corrigido. Onde o comportamento é questionável fica marcado com
`# DEVIDA-TECNICA: Dn`, a remeter para `docs/divida-tecnica.md`.

Convenções que estes testes fixam
--------------------------------

- A comparação é `palavra_chave.upper() in descricao.upper()` nos dois lados:
  insensível a maiúsculas e minúsculas, mas **sem dobrar acentos**. `"cafe"` não
  casa com `"CAFÉ"`; `"café"` casa. Regra vazia é o caso limite de `"x" in s`,
  que é sempre verdadeiro.
- A **primeira** regra que casa ganha, e o `break` é incondicional — ver o
  cenário da categoria diferente, que é a D7.
- A precedência entre as duas fases é fixa pelo código, não pela ordem da
  lista: exclusão antes de categorização, sempre. A ordem dentro de cada fase
  é a da lista que o `importar_transacoes` (linha 26) recebe do SQLite sem
  `ORDER BY`, o que é a outra metade da D7 e não é testado aqui.

Números escolhidos
------------------

Identificadores inteiros escritos à mão: 1, 2 e 5 para categorias; 10, 20, 21,
30 e 99 para subcategorias. Os valores não são reais da base de dados e não
dependem de nenhuma tabela. As datas são fixas em 2025: nenhum teste assenta na
data de hoje.

Todos os valores esperados são calculados à mão e escritos como constantes, com
o cálculo no comentário de cada teste.
"""

from datetime import date
from types import SimpleNamespace

from importador_transacoes import aplicar_regras


# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------

def regra(palavra_chave, categoria_id=None, subcategoria_id=None):
    """Regra com os mesmos nomes de campo que `RegraCategorizacao`.

    `categoria_id=None` é a regra de exclusão, pela convenção das linhas 8-9.
    """
    return SimpleNamespace(
        palavra_chave=palavra_chave,
        categoria_id=categoria_id,
        subcategoria_id=subcategoria_id,
    )


def transacao(descricao, categoria_id=None, subcategoria_id=None,
              ano=2025, mes=3, dia=10):
    """Transação com os mesmos nomes de campo que `Transacao`.

    A data é fixa e não é lida por `aplicar_regras`; existe para que o objecto
    se pareça com o que `importar_transacoes` constrói na linha 50.
    """
    return SimpleNamespace(
        data=date(ano, mes, dia),
        descricao=descricao,
        valor=-12.75,
        saldo=100.0,
        categoria_id=categoria_id,
        subcategoria_id=subcategoria_id,
    )


# ---------------------------------------------------------------------------
# Fase 2 — a regra que casa atribui
# ---------------------------------------------------------------------------

def test_regra_que_casa_atribui_categoria_e_subcategoria():
    """Regra que casa, transação sem categoria: atribui as duas coisas.

    Cálculo à mão:
      fase 1: a regra tem categoria_id = 1, logo é saltada (linhas 8-9)
      fase 2: não é de exclusão; "UBER" em "COMPRA UBER EATS".upper() -> casa
      linha 18: categoria_id is None -> verdadeiro
      escreve categoria_id = 1 (linha 19) e subcategoria_id = 10 (linha 20)
      linha 23: break
    """
    t = transacao("COMPRA UBER EATS")
    aplicar_regras(t, [regra("uber", 1, 10)])

    assert (t.categoria_id, t.subcategoria_id) == (1, 10)


def test_regra_que_nao_casa_nao_atribui_nada():
    """Palavra-chave ausente da descrição: a transação fica por categorizar.

    Cálculo à mão:
      fase 2: "UBER" em "PADARIA DO BAIRRO".upper() -> falso
      nenhum if entra, o for termina sem escrever
      esperado: os dois a None
    """
    t = transacao("PADARIA DO BAIRRO")
    aplicar_regras(t, [regra("uber", 1, 10)])

    assert (t.categoria_id, t.subcategoria_id) == (None, None)


def test_comparacao_ignora_maiusculas_nos_dois_sentidos():
    """A comparação é feita em maiúsculas dos dois lados.

    Cálculo à mão, dois objectos novos com os mesmos valores:
      caso A: palavra-chave "netflix", descrição "NETFLIX.COM DEBITO"
              "NETFLIX" em "NETFLIX.COM DEBITO" -> casa, linha 18 -> (1, 10)
      caso B: palavra-chave "NETFLIX", descrição "netflix.com debito"
              "NETFLIX" em "NETFLIX.COM DEBITO" -> casa, linha 18 -> (1, 10)
    """
    t_a = transacao("NETFLIX.COM DEBITO")
    t_b = transacao("netflix.com debito")

    aplicar_regras(t_a, [regra("netflix", 1, 10)])
    aplicar_regras(t_b, [regra("NETFLIX", 1, 10)])

    assert (t_a.categoria_id, t_a.subcategoria_id) == (1, 10)
    assert (t_b.categoria_id, t_b.subcategoria_id) == (1, 10)


def test_regra_com_acento_casa_descricao_maiuscula():
    """`upper()` não deita fora os acentos: a palavra acentuada casa.

    # DEVIDA-TECNICA: D8 (lado b) — a importação casa o "ç" e o "é", porque a
    comparação é `upper()`; o backfill de `routers/regras.py:54` usa `ilike`,
    que é ASCII-only e não casa. A mesma regra funciona na importação e falha
    no backfill.

    Cálculo à mão:
      fase 2: palavra_chave "café" -> "CAFÉ"; descrição "CAFÉ PASTELARIA"
              "CAFÉ" em "CAFÉ PASTELARIA" -> casa na posição 0
      linha 18: categoria_id is None -> escreve (1, 10)
    """
    t = transacao("CAFÉ PASTELARIA")
    aplicar_regras(t, [regra("café", 1, 10)])

    assert (t.categoria_id, t.subcategoria_id) == (1, 10)


def test_regra_sem_acento_nao_casa_descricao_com_acento():
    """O limite de 4a: trocar o acento pela letra base deixa de casar.

    Cálculo à mão:
      mesma descrição, palavra-chave "cafe" -> "CAFE"
      "CAFE" em "CAFÉ PASTELARIA" -> falso: é "CAFE" contra "CAFÉ PASTELARIA",
      a quarta letra é "É" e não "E"
      nenhum if entra; esperado (None, None)
    """
    t = transacao("CAFÉ PASTELARIA")
    aplicar_regras(t, [regra("cafe", 1, 10)])

    assert (t.categoria_id, t.subcategoria_id) == (None, None)


def test_a_primeira_regra_que_casa_ganha():
    """Com três regras que casam na mesma descrição, vence a primeira da lista.

    Cálculo à mão, pela ordem em que as regras são percorridas:
      regra 1 "mercado"      -> "MERCADO" em "MERCADO CENTRAL LISBOA" -> casa
                               linha 18: transação sem categoria -> (1, 10)
                               linha 23: break, o ciclo acaba aqui
      regra 2 "mercado central" e regra 3 "central" também casariam, mas nunca
      são avaliadas
    """
    t = transacao("MERCADO CENTRAL LISBOA")
    aplicar_regras(t, [
        regra("mercado", 1, 10),
        regra("mercado central", 2, 20),
        regra("central", 3, 30),
    ])

    assert (t.categoria_id, t.subcategoria_id) == (1, 10)


def test_break_impede_a_segunda_regra_de_atribuir_a_subcategoria():
    """Regra 1.ª sem subcategoria: a 2.ª traria a subcategoria, o break não deixa.

    # DEVIDA-TECNICA: D7 (o `break` da fase 2) — este teste só passa porque o
    `break` da linha 23 existe. A 2.ª regra também casa, e entraria pelo ramo da
    linha 21, que é exactamente o ramo que escreve a subcategoria; é o `break` que
    impede a escrita. É o par com
    `test_regra_consumida_sem_atribuir_deixa_a_transacao_sem_subcategoria`, que
    fixa o mesmo `break` pelo lado da transação já categorizada.

    Cálculo à mão, com a lista tal e qual:
      descricao "MERCADO CENTRAL LISBOA"
      fase 1: as duas regras têm categoria_id (1 e 1), logo ambas são saltadas
              (linhas 8-9); a fase 1 não escreve nada
      fase 2, regra 1 "mercado" (categoria_id=1, subcategoria_id=None):
        linha 17: "MERCADO" em "MERCADO CENTRAL LISBOA" -> casa na posição 0
        linha 18: transacao.categoria_id é None -> verdadeiro
        linha 19: categoria_id = 1
        linha 20: subcategoria_id = None, porque a regra 1 não tem subcategoria
        linha 23: break
      a regra 2 "mercado central" (categoria_id=1, subcategoria_id=20) nunca é
      avaliada. E se fosse, casaria: "MERCADO CENTRAL" em "MERCADO CENTRAL
      LISBOA" -> casa na posição 0. Entraria pelo ramo da linha 21 com
      1 == 1 verdadeiro e subcategoria_id ainda None -> escreveria 20.
      esperado: (1, None)
      sem o break da linha 23 o resultado seria (1, 20)
    """
    t = transacao("MERCADO CENTRAL LISBOA")
    aplicar_regras(t, [
        regra("mercado", 1, None),
        regra("mercado central", 1, 20),
    ])

    assert (t.categoria_id, t.subcategoria_id) == (1, None)


# ---------------------------------------------------------------------------
# Fase 2 — a transação já vem categorizada
# ---------------------------------------------------------------------------

def test_mesma_categoria_sem_subcategoria_atribui_subcategoria():
    """Categoria já certa, subcategoria a None: só a subcategoria é escrita.

    Cálculo à mão:
      fase 1: a regra tem categoria_id = 2, saltada
      fase 2: "METRO" em "CARGA METRO LISBOA" -> casa
      linha 18: categoria_id é 2, não None -> falso
      linha 21: 2 == 2 e subcategoria_id is None -> verdadeiro
      escreve subcategoria_id = 20 (linha 22); categoria_id fica 2
      esperado: (2, 20)
    """
    t = transacao("CARGA METRO LISBOA", categoria_id=2)
    aplicar_regras(t, [regra("metro", 2, 20)])

    assert (t.categoria_id, t.subcategoria_id) == (2, 20)


def test_categoria_e_subcategoria_iguais_mudam_nada():
    """Já com a mesma categoria e subcategoria: nada é reescrito.

    Cálculo à mão:
      fase 2: "METRO" casa
      linha 18: falso, a categoria não é None
      linha 21: a categoria bate, mas subcategoria_id é 20 e não None -> falso
      linha 23: o break consome a regra na mesma
      esperado: (2, 20) — a subcategoria 99 da regra nunca é escrita
    """
    t = transacao("CARGA METRO LISBOA", categoria_id=2, subcategoria_id=20)
    aplicar_regras(t, [regra("metro", 2, 99)])

    assert (t.categoria_id, t.subcategoria_id) == (2, 20)


def test_categoria_diferente_nao_atribui_e_gasta_a_regra():
    """Categoria diferente: nada é atribuído e a regra seguinte é ignorada.

    # DEVIDA-TECNICA: D7 — o `break` da linha 23 é incondicional: está dentro
    # do `if` de correspondência (linha 17) e não dentro de nenhum dos ramos de
    # atribuição. "Casou" não é "atribuiu", e a diferença de consequência é uma
    transação já categorizada que fica sem a subcategoria que a 2.ª regra lhe
    traria, sem erro nem registo.

    Cálculo à mão:
      regra 1 "metro": "METRO" casa
        linha 18: falso (a categoria é 5, não None)
        linha 21: 5 != 2 -> falso
        nada escrito; linha 23: break
      regra 2 "lisboa": "LISBOA" também caberia na descrição, mas o break já
      acabou o ciclo — nunca é avaliada, e traria a subcategoria 21
      esperado: (5, None), sem subcategoria
    """
    t = transacao("CARGA METRO LISBOA", categoria_id=5)
    aplicar_regras(t, [
        regra("metro", 2, 20),
        regra("lisboa", 2, 21),
    ])

    assert (t.categoria_id, t.subcategoria_id) == (5, None)


def test_regra_consumida_sem_atribuir_deixa_a_transacao_sem_subcategoria():
    """A 1.ª regra casa com outra categoria e consome o ciclo; a 2.ª traria a sub.

    # DEVIDA-TECNICA: D7 (regra consumida sem atribuir) — este teste fixa o caso
    em que a consequência é visível numa transação que o utilizador já tinha
    classificado à mão: ela fica com categoria mas sem subcategoria, e a 2.ª regra
    —que era exactamente a que lhe servia— nunca chega a ser avaliada. Sem o
    `break` da linha 23 a subcategoria 50 era escrita.

    Cálculo à mão, com a lista tal e qual:
      descricao "METRO LISBOA"; a transação já vem com categoria_id=5 e
      subcategoria_id=None
      fase 1: as duas regras têm categoria_id (2 e 5), logo ambas são saltadas
              (linhas 8-9); a fase 1 não escreve nada
      fase 2, regra 1 "metro" (categoria_id=2, subcategoria_id=20):
        linha 17: "METRO" em "METRO LISBOA" -> casa na posição 0
        linha 18: a categoria é 5, não None -> falso
        linha 21: 5 == 2 -> falso, logo o elif não entra
        nada escrito — a regra "casou" mas não atribuiu
        linha 23: break
      a regra 2 "lisboa" (categoria_id=5, subcategoria_id=50) nunca é avaliada. E
      se fosse, casaria: "LISBOA" em "METRO LISBOA" -> casa na posição 6.
      Entraria pelo ramo da linha 21 com 5 == 5 verdadeiro e subcategoria_id
      None -> escreveria 50.
      esperado: (5, None) — a categoria que já lá estava é a que fica
      sem o break da linha 23 o resultado seria (5, 50)
    """
    t = transacao("METRO LISBOA", categoria_id=5)
    aplicar_regras(t, [
        regra("metro", 2, 20),
        regra("lisboa", 5, 50),
    ])

    assert (t.categoria_id, t.subcategoria_id) == (5, None)


# ---------------------------------------------------------------------------
# Fase 1 — regras de exclusão
# ---------------------------------------------------------------------------

def test_regra_de_exclusao_deixa_a_transacao_por_categorizar():
    """Regra de exclusão que casa: a fase 2 nem corre.

    Cálculo à mão:
      fase 1: a regra tem categoria_id None, logo não é saltada (linha 8)
      linha 10: "TRANSFERENCIA" em "TRANSFERENCIA PARA O TB" -> casa
      linha 11: return imediato; a fase 2 não chega a começar
      nada foi escrito: esperado (None, None)
    """
    t = transacao("TRANSFERENCIA PARA O TB")
    aplicar_regras(t, [regra("transferencia")])

    assert (t.categoria_id, t.subcategoria_id) == (None, None)


def test_regra_de_exclusao_mantem_a_categoria_que_ja_existe():
    """O `return` da exclusão não limpa a transação: fixa o código, não o comentário.

    Nota: o comentário da linha 6 de `importador_transacoes.py` diz que a
    transação "fica sem categoria", mas o `return` da linha 11 não escreve
    nada. O que este teste fixa é o que o código faz: uma transação que já
    tivesse categoria mantém a sua, e a mesma fica sem subcategoria.

    Cálculo à mão:
      fase 1: a regra de exclusão "refeicao" casa em "REFEICAO TRABALHO"
      linha 11: return; nada é escrito em nenhum dos dois campos
      esperado: (2, 20) — os valores que a transação já trazia
    """
    t = transacao("REFEICAO TRABALHO", categoria_id=2, subcategoria_id=20)
    aplicar_regras(t, [regra("refeicao")])

    assert (t.categoria_id, t.subcategoria_id) == (2, 20)


def test_regra_de_exclusao_ganha_mesmo_listada_depois():
    """A precedência entre fases é do código, não da ordem da lista.

    Cálculo à mão:
      lista: [regra de categorização "bica" (1, 10), regra de exclusão "bica xp"]
      fase 1: "bica" é saltada por ter categoria_id = 1; "bica xp" casa com
              "BICA XP CERVEJA" -> return na linha 11
      a regra de categorização, apesar de vir primeiro na lista, nunca chega a
      ser avaliada na fase 2
      esperado: (None, None), e não (1, 10)
    """
    t = transacao("BICA XP CERVEJA")
    aplicar_regras(t, [
        regra("bica", 1, 10),
        regra("bica xp"),
    ])

    assert (t.categoria_id, t.subcategoria_id) == (None, None)


# ---------------------------------------------------------------------------
# Casos limite
# ---------------------------------------------------------------------------

def test_lista_de_regras_vazia_nao_faz_nada():
    """Sem regras, os dois `for` não correm e a transação não é tocada.

    Cálculo à mão:
      linha 7: `for regra in []` não entra
      linha 14: `for regra in []` também não entra
      a função devolve None; nenhum atributo é escrito
      esperado: (None, None)
    """
    t = transacao("COMPRA UBER EATS")
    assert aplicar_regras(t, []) is None

    assert (t.categoria_id, t.subcategoria_id) == (None, None)


def test_palavra_chave_vazia_casa_em_tudo():
    """Uma regra com palavra-chave vazia casa em qualquer descrição.

    # DEVIDA-TECNICA: D21 — este teste fixa o comportamento **actual** (não o
    desejado). A palavra-chave vazia nunca é validada no servidor: o schema
    (`schemas.py:57`) é um `str` sem `min_length`, o modelo (`database.py:198`)
    só impõe `nullable=False` e `unique=True`, e a rota (`routers/regras.py:35`
    e 40-43) grava o valor tal e qual. A única barreira é o `trim()` do
    formulário, em `frontend/src/pages/Regras.jsx:48` e 51, que se contorna com
    uma chamada directa à API. Se a D21 for decidida no sentido de validar
    `palavra_chave`, este teste passa a falhar de propósito.

    Cálculo à mão:
      linha 10/17: "" em qualquer cadeia é verdadeiro, pela definição de `in`
      fase 1: a regra tem categoria_id = 1, logo é saltada (linhas 8-9)
      fase 2, com a regra vazia e categoria_id = 1:
        linha 18: a transação está sem categoria -> escreve (1, 10)
      a descrição não tem nada que ver com a regra e mesmo assim é categorizada
    """
    t = transacao("TRANSFERENCIA PARA O TB")
    aplicar_regras(t, [regra("", 1, 10)])

    assert (t.categoria_id, t.subcategoria_id) == (1, 10)
