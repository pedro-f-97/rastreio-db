"""Testes de caracterização do cálculo FIFO do património.

Fixam o comportamento **actual** de `GET /api/ativos/{id}/resumo`, que se apoia
em `_resumo_valor_ativo` (`backend/servicos/patrimonio_serv.py:13`). Servem
para que mexer no cálculo não mude nada sem dar conta: se um destes testes
falhar, a mudança foi de propósito e tem de ser justificada.

Nada aqui é corrigido. Onde o comportamento é questionável, fica marcado com
`# DEVIDA-TECNICA: Dn`, a remeter para `docs/divida-tecnica.md`.

Convenção de sinais, afirmada em todos os testes
------------------------------------------------
O que a aplicação grava e o que a aplicação devolve não são a mesma coisa:

* O frontend grava `valor_total` **negativo nas compras** e positivo nas vendas
  e nos dividendos (`frontend/src/pages/Ativos.jsx:133-144`: sinal -1 na
  compra, e a comissão entra também com sinal negativo).
* `_resumo_valor_ativo` normaliza com `abs()` (linhas 37 e 68), por isso
  -100,00 e +100,00 valem o mesmo custo de aquisição.
* `custo_base` é interno e **sempre positivo**.
* `custo_total` na resposta é `round(-custo_base, 2)`, portanto **negativo** por
  convenção (ver `DEVIDA-TECNICA: D12a`, em `routers/patrimonio.py:198`).
* `latente = valor_atual - custo_base`.
* `mais_menos_valia = round(realizado + latente, 2)`, em que `realizado` já
  traz o sinal: ganho positivo, perda negativa.

Os valores esperados são calculados à mão e escritos como constantes; o cálculo
está no comentário de cada teste. Entra-se pelo endpoint real, e não pela função
interna, para que a convenção de sinais fique fixada também.

Há uma excepção, no cenário 18: chama a função interna de propósito. A
tolerância de `1e-9` que esgota os lotes vive dentro dela, e o router arredonda
`quantidade` a 6 casas e `custo_base` a 2, o que oculta esse efeito. Um teste
pelo endpoint não a conseguiria ver.
"""

from datetime import date

from database import (
    Ativo,
    MovimentoAtivo,
    PrecoAtivo,
    TipoAtivo,
    TipoContabilizacao,
    TipoMovimento,
)
from servicos.patrimonio_serv import _resumo_valor_ativo

# Preço transversal à maioria dos cenários: 20,00 por unidade.
PRECO_UNITARIO = 20.00
DATA_PRECO = date(2025, 6, 1)


# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------

def semear_tipo(session, nome, tem_unidades):
    tipo = TipoAtivo(nome=nome, tem_unidades=tem_unidades)
    session.add(tipo)
    session.commit()
    return tipo


def semear_ativo(session, nome, tipo):
    contabilizacao = (
        TipoContabilizacao.investimento
        if tipo.tem_unidades
        else TipoContabilizacao.patrimonio
    )
    ativo = Ativo(nome=nome, tipo_id=tipo.id, contabilizacao=contabilizacao)
    session.add(ativo)
    session.commit()
    return ativo


def semear_movimento(session, ativo, tipo_movimento, data, valor_total,
                     quantidade=None, comissao=None):
    """Grava um movimento com o sinal que o frontend realmente envia."""
    movimento = MovimentoAtivo(
        ativo_id=ativo.id,
        tipo_movimento=tipo_movimento,
        data=data,
        quantidade=quantidade,
        preco_unitario=None,
        comissao=comissao,
        valor_total=valor_total,
    )
    session.add(movimento)
    session.commit()
    return movimento


def semear_preco(session, ativo, data, preco):
    registo = PrecoAtivo(ativo_id=ativo.id, data=data, preco=preco)
    session.add(registo)
    session.commit()
    return registo


def confirmar_resumo(resumo, *, quantidade, custo_total, valor_atual,
                     realizado, latente, mais_menos_valia):
    """Confirma cada campo contra uma constante calculada à mão.

    Os argumentos têm nome explícito e em separado, para que o sinal de cada um
    fique à vista na chamada. Aqui não se calcula nada.
    """
    assert resumo["quantidade"] == quantidade, (
        f"quantidade: esperado {quantidade}, veio {resumo['quantidade']}"
    )
    assert resumo["custo_total"] == custo_total, (
        f"custo_total (negativo por convenção, D12a): esperado {custo_total}, "
        f"veio {resumo['custo_total']}"
    )
    assert resumo["valor_atual"] == valor_atual, (
        f"valor_atual: esperado {valor_atual}, veio {resumo['valor_atual']}"
    )
    assert resumo["realizado"] == realizado, (
        f"realizado: esperado {realizado}, veio {resumo['realizado']}"
    )
    assert resumo["latente"] == latente, (
        f"latente: esperado {latente}, veio {resumo['latente']}"
    )
    assert resumo["mais_menos_valia"] == mais_menos_valia, (
        f"mais_menos_valia: esperado {mais_menos_valia}, veio "
        f"{resumo['mais_menos_valia']}"
    )


def pedir_resumo(client, ativo):
    # O router de patrimonio tem prefixo proprio (`routers/patrimonio.py:14`),
    # por isso o caminho completo leva "/patrimonio" antes dos "/ativos".
    resposta = client.get(f"/api/patrimonio/ativos/{ativo.id}/resumo")
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


# ---------------------------------------------------------------------------
# 1. Lote unico
# ---------------------------------------------------------------------------

def test_lote_unico_sem_vendas(client, session):
    """Uma compra e nenhuma venda: a posicao inteira esta no lote.

    Calculo a mao:
      custo_unitario = abs(-100,00) / 10 = 10,00
      custo_base     = 10 x 10,00       = 100,00
      custo_total    = -100,00  (negativo, D12a)
      valor_atual    = round(10 x 20,00, 2) = 200,00
      latente        = 200,00 - 100,00 = +100,00
      realizado      = 0,00  (nada foi vendido)
      mais_menos_valia = 0,00 + 100,00 = +100,00
    """
    tipo = semear_tipo(session, "Acoes", tem_unidades=True)
    ativo = semear_ativo(session, "Acoes X", tipo)
    semear_movimento(session, ativo, TipoMovimento.compra, date(2025, 1, 10),
                     valor_total=-100.00, quantidade=10)
    semear_preco(session, ativo, DATA_PRECO, PRECO_UNITARIO)

    resumo = pedir_resumo(client, ativo)

    confirmar_resumo(
        resumo,
        quantidade=10.0,
        custo_total=-100.00,
        valor_atual=200.00,
        realizado=0.0,
        latente=100.00,
        mais_menos_valia=100.00,
    )
    assert resumo["preco_atual"] == 20.00
    assert resumo["data_preco"] == "2025-06-01"


# ---------------------------------------------------------------------------
# 2. Multi-lote
# ---------------------------------------------------------------------------

def test_multi_lote_soma_o_custo_das_compras(client, session):
    """Duas compras a precos diferentes, ainda sem vendas.

    Calculo a mao:
      lote 1: custo_unitario = abs(-100,00) / 10 = 10,00
      lote 2: custo_unitario = abs(-300,00) / 10 = 30,00
      custo_base  = 10 x 10,00 + 10 x 30,00 = 100,00 + 300,00 = 400,00
      custo_total = -400,00  (negativo, D12a)
      valor_atual = round(20 x 20,00, 2) = 400,00
      latente     = 400,00 - 400,00 = 0,00
      mais_menos_valia = 0,00 + 0,00 = 0,00

    O preco actual (20,00) e a media simples das compras (20,00), por isso o
    latente fecha a zero. E coincidencia dos numeros escolhidos, nao uma
    propriedade do FIFO.
    """
    tipo = semear_tipo(session, "Acoes", tem_unidades=True)
    ativo = semear_ativo(session, "Acoes Y", tipo)
    semear_movimento(session, ativo, TipoMovimento.compra, date(2025, 1, 10),
                     valor_total=-100.00, quantidade=10)
    semear_movimento(session, ativo, TipoMovimento.compra, date(2025, 3, 10),
                     valor_total=-300.00, quantidade=10)
    semear_preco(session, ativo, DATA_PRECO, PRECO_UNITARIO)

    resumo = pedir_resumo(client, ativo)

    confirmar_resumo(
        resumo,
        quantidade=20.0,
        custo_total=-400.00,
        valor_atual=400.00,
        realizado=0.0,
        latente=0.00,
        mais_menos_valia=0.00,
    )


# ---------------------------------------------------------------------------
# 3. Venda que atravessa dois lotes
# ---------------------------------------------------------------------------

def test_venda_atravessa_dois_lotes_consome_o_mais_antigo_primeiro(client, session):
    """Vende 15 unidades com 10 num lote e 10 noutro.

    Calculo a mao (FIFO: o lote mais antigo e consumido primeiro):
      lote 1, o mais antigo, a 10,00: consome 10, logo 10 x 10,00 = 100,00
      faltam 5; lote 2, a 30,00: consome 5, logo 5 x 30,00 = 150,00
      custo_vendido  = 100,00 + 150,00 = 250,00
      q_efetiva = 15 (houve lotes para todo o lado, nada ficou por consumir)
      valor_efetivo  = abs(450,00) x (15 / 15) = 450,00
      realizado      = 450,00 - 250,00 = +200,00
      resta o lote 2 com 5 unidades a 30,00: custo_base = 5 x 30,00 = 150,00
      custo_total = -150,00  (negativo, D12a)
      valor_atual = round(5 x 20,00, 2) = 100,00
      latente     = 100,00 - 150,00 = -50,00
        (perda nao realizada: as 5 que restam custaram 30,00 e valem 20,00)
      mais_menos_valia = 200,00 + (-50,00) = +150,00
    """
    tipo = semear_tipo(session, "Acoes", tem_unidades=True)
    ativo = semear_ativo(session, "Acoes Z", tipo)
    semear_movimento(session, ativo, TipoMovimento.compra, date(2025, 1, 10),
                     valor_total=-100.00, quantidade=10)
    semear_movimento(session, ativo, TipoMovimento.compra, date(2025, 3, 10),
                     valor_total=-300.00, quantidade=10)
    semear_movimento(session, ativo, TipoMovimento.venda, date(2025, 4, 10),
                     valor_total=450.00, quantidade=15)
    semear_preco(session, ativo, DATA_PRECO, PRECO_UNITARIO)

    resumo = pedir_resumo(client, ativo)

    confirmar_resumo(
        resumo,
        quantidade=5.0,
        custo_total=-150.00,
        valor_atual=100.00,
        realizado=200.00,
        latente=-50.00,
        mais_menos_valia=150.00,
    )


# ---------------------------------------------------------------------------
# 4. Venda parcial dentro de um unico lote
# ---------------------------------------------------------------------------

def test_venda_parcial_dentro_de_um_lote(client, session):
    """Vende 4 das 10 unidades de um so lote.

    Calculo a mao:
      custo_vendido  = 4 x 10,00 = 40,00
      q_efetiva = 4 (o lote tinha 10, deu para consumir)
      valor_efetivo  = abs(100,00) x (4 / 4) = 100,00
      realizado      = 100,00 - 40,00 = +60,00
      resta o lote com 6 unidades a 10,00: custo_base = 6 x 10,00 = 60,00
      custo_total = -60,00  (negativo, D12a)
      valor_atual = round(6 x 20,00, 2) = 120,00
      latente     = 120,00 - 60,00 = +60,00
      mais_menos_valia = 60,00 + 60,00 = +120,00
    """
    tipo = semear_tipo(session, "Acoes", tem_unidades=True)
    ativo = semear_ativo(session, "Acoes W", tipo)
    semear_movimento(session, ativo, TipoMovimento.compra, date(2025, 1, 10),
                     valor_total=-100.00, quantidade=10)
    semear_movimento(session, ativo, TipoMovimento.venda, date(2025, 4, 10),
                     valor_total=100.00, quantidade=4)
    semear_preco(session, ativo, DATA_PRECO, PRECO_UNITARIO)

    resumo = pedir_resumo(client, ativo)

    confirmar_resumo(
        resumo,
        quantidade=6.0,
        custo_total=-60.00,
        valor_atual=120.00,
        realizado=60.00,
        latente=60.00,
        mais_menos_valia=120.00,
    )


# ---------------------------------------------------------------------------
# 5. Venda total
# ---------------------------------------------------------------------------

def test_venda_total_zera_a_posicao(client, session):
    """Vende tudo: a posicao vai a zero, mas o realizado fica registado.

    Calculo a mao:
      custo_vendido  = 10 x 10,00 = 100,00
      valor_efetivo  = abs(250,00) x (10 / 10) = 250,00
      realizado      = 250,00 - 100,00 = +150,00
      lotes esgotados, logo quantidade = 0,0 e custo_base = 0,0
      custo_total = round(-0,0, 2), que em Python e -0,0 e compara igual a 0,0
      valor_atual = 0,0 (so ha valor quando a quantidade e maior que zero)
      latente = 0,0 - 0,0 = 0,0
      mais_menos_valia = 150,00 + 0,0 = +150,00

    Existe preco, por isso `latente` e 0,0 e nao None. O ganho da venda nao se
    perde: sobrevive no `realizado` e chega ao `mais_menos_valia`.
    """
    tipo = semear_tipo(session, "Acoes", tem_unidades=True)
    ativo = semear_ativo(session, "Acoes V", tipo)
    semear_movimento(session, ativo, TipoMovimento.compra, date(2025, 1, 10),
                     valor_total=-100.00, quantidade=10)
    semear_movimento(session, ativo, TipoMovimento.venda, date(2025, 4, 10),
                     valor_total=250.00, quantidade=10)
    semear_preco(session, ativo, DATA_PRECO, PRECO_UNITARIO)

    resumo = pedir_resumo(client, ativo)

    confirmar_resumo(
        resumo,
        quantidade=0.0,
        custo_total=0.0,
        valor_atual=0.0,
        realizado=150.00,
        latente=0.0,
        mais_menos_valia=150.00,
    )


# ---------------------------------------------------------------------------
# 6. Sobre-venda
# ---------------------------------------------------------------------------

def test_sobre_venda_escala_o_encaixe_e_nunca_avisa(client, session):
    """Vende 15 unidades tendo 10.

    Calculo a mao:
      consome as 10 do lote: custo_vendido = 10 x 10,00 = 100,00
      faltam 5 e nao ha mais lotes, por isso o ciclo termina
      q_efetiva = 15 - 5 = 10
      valor_efetivo  = abs(300,00) x (10 / 15) = 200,00
      realizado      = 200,00 - 100,00 = +100,00
      lotes esgotados, logo quantidade = 0,0 e custo_base = 0,0

    As 5 unidades que nao existiam e 100,00 de encaixe desaparecem sem erro,
    sem aviso e sem registo: o resultado e identico ao de ter vendido 10
    unidades por 200,00.

    DEVIDA-TECNICA: D15 (sobre-venda silenciosa). A decisao entre avisar e
    recusar a operacao esta pendente, por isso este teste fixa o
    comportamento actual e nao o desejado.
    """
    tipo = semear_tipo(session, "Acoes", tem_unidades=True)
    ativo = semear_ativo(session, "Acoes U", tipo)
    semear_movimento(session, ativo, TipoMovimento.compra, date(2025, 1, 10),
                     valor_total=-100.00, quantidade=10)
    semear_movimento(session, ativo, TipoMovimento.venda, date(2025, 4, 10),
                     valor_total=300.00, quantidade=15)
    semear_preco(session, ativo, DATA_PRECO, PRECO_UNITARIO)

    resumo = pedir_resumo(client, ativo)

    confirmar_resumo(
        resumo,
        quantidade=0.0,
        custo_total=0.0,
        valor_atual=0.0,
        realizado=100.00,
        latente=0.0,
        mais_menos_valia=100.00,
    )


# ---------------------------------------------------------------------------
# 7. Dividendo
# ---------------------------------------------------------------------------

def test_dividendo_entra_no_realizado(client, session):
    """Um dividendo soma ao realizado e nao toca nos lotes.

    Calculo a mao:
      o dividendo soma com abs(): realizado = abs(25,00) = +25,00
      o lote fica intacto: custo_base = 10 x 10,00 = 100,00
      custo_total = -100,00  (negativo, D12a)
      valor_atual = round(10 x 20,00, 2) = 200,00
      latente     = 200,00 - 100,00 = +100,00
      mais_menos_valia = 25,00 + 100,00 = +125,00

    Nota: o rendimento entra no mesmo campo que a mais/menos-valia das vendas,
    e dai no mesmo `mais_menos_valia`. Um dividendo e um ganho de capital ficam
    assim indistinguiveis para quem le o resumo.
    """
    tipo = semear_tipo(session, "Acoes", tem_unidades=True)
    ativo = semear_ativo(session, "Acoes T", tipo)
    semear_movimento(session, ativo, TipoMovimento.compra, date(2025, 1, 10),
                     valor_total=-100.00, quantidade=10)
    semear_movimento(session, ativo, TipoMovimento.dividendo, date(2025, 5, 10),
                     valor_total=25.00)
    semear_preco(session, ativo, DATA_PRECO, PRECO_UNITARIO)

    resumo = pedir_resumo(client, ativo)

    confirmar_resumo(
        resumo,
        quantidade=10.0,
        custo_total=-100.00,
        valor_atual=200.00,
        realizado=25.00,
        latente=100.00,
        mais_menos_valia=125.00,
    )


# ---------------------------------------------------------------------------
# 8. Ativo sem unidades
# ---------------------------------------------------------------------------

def test_ativo_sem_unidades_usa_o_valor_total_como_custo(client, session):
    """Um bem sem unidades: o preco registado e o valor do bem inteiro.

    Calculo a mao (ramo dos bens, `patrimonio_serv.py:29-58`):
      custo_base = abs(-15000,00) = 15 000,00  (a compra soma o valor todo)
      nao houve venda, logo `vendido` e falso e o custo e positivo
      valor_atual = round(15 000,00, 2) = 15 000,00  (o preco, nao um unitario)
      custo_total = -15 000,00  (negativo, D12a)
      latente     = 15 000,00 - 15 000,00 = 0,00
      mais_menos_valia = 0,00 + 0,00 = 0,00
      quantidade = 0,0 sempre: este ramo nao conta unidades
    """
    tipo = semear_tipo(session, "Imovel", tem_unidades=False)
    ativo = semear_ativo(session, "Casa", tipo)
    semear_movimento(session, ativo, TipoMovimento.compra, date(2025, 1, 10),
                     valor_total=-15000.00)
    semear_preco(session, ativo, DATA_PRECO, 15000.00)

    resumo = pedir_resumo(client, ativo)

    confirmar_resumo(
        resumo,
        quantidade=0.0,
        custo_total=-15000.00,
        valor_atual=15000.00,
        realizado=0.0,
        latente=0.00,
        mais_menos_valia=0.00,
    )


# ---------------------------------------------------------------------------
# 9. Sem preco disponivel
# ---------------------------------------------------------------------------

def test_sem_preco_degrada_o_latente_para_nulo(client, session):
    """Sem registo de preco: valor a zero e latente nulo.

    Calculo a mao:
      custo_base = 10 x 10,00 = 100,00  (o FIFO corre todo)
      valor_atual = 0,0 porque nao ha preco (so ha valor quando ha preco e
                    quantidade maior que zero)
      custo_total = -100,00  (negativo, D12a)
      latente = None, porque `preco_atual` e None
      mais_menos_valia = round(0,00 + 0,0, 2) = 0,00, o `ou 0,0` converte
        o latente nulo em zero

    Os 100,00 de custo nao aparecem em lado nenhum: nem no valor, nem no
    latente, nem no mais/menos-valia.

    DEVIDA-TECNICA: D12b (latente nulo degrada o mais/menos-valia).
    """
    tipo = semear_tipo(session, "Acoes", tem_unidades=True)
    ativo = semear_ativo(session, "Acoes S", tipo)
    semear_movimento(session, ativo, TipoMovimento.compra, date(2025, 1, 10),
                     valor_total=-100.00, quantidade=10)

    resumo = pedir_resumo(client, ativo)

    confirmar_resumo(
        resumo,
        quantidade=10.0,
        custo_total=-100.00,
        valor_atual=0.0,
        realizado=0.0,
        latente=None,
        mais_menos_valia=0.0,
    )
    assert resumo["preco_atual"] is None
    assert resumo["data_preco"] is None


# ---------------------------------------------------------------------------
# 10. O abs() normaliza o sinal
# ---------------------------------------------------------------------------

def test_abs_normaliza_o_sinal_do_valor_total(client, session):
    """Uma compra com sinal oposto ao da aplicacao da o mesmo resultado.

    O frontend grava compras negativas, mas `_resumo_valor_ativo` faz
    abs() (linha 68), por isso o sinal de `valor_total` e irrelevante para o
    calculo. Este cenario e o espelho do cenario 1, com +100,00 em vez de
    -100,00, e tem de dar exactamente os mesmos numeros.

    Calculo a mao:
      abs(+100,00) = 100,00, logo custo_unitario = 100,00 / 10 = 10,00
      custo_base = 10 x 10,00 = 100,00
      custo_total = -100,00  (negativo, D12a)
      valor_atual = round(10 x 20,00, 2) = 200,00
      latente = 200,00 - 100,00 = +100,00
      mais_menos_valia = 0,00 + 100,00 = +100,00
    """
    tipo = semear_tipo(session, "Acoes", tem_unidades=True)
    ativo = semear_ativo(session, "Acoes R", tipo)
    semear_movimento(session, ativo, TipoMovimento.compra, date(2025, 1, 10),
                     valor_total=100.00, quantidade=10)
    semear_preco(session, ativo, DATA_PRECO, PRECO_UNITARIO)

    resumo = pedir_resumo(client, ativo)

    confirmar_resumo(
        resumo,
        quantidade=10.0,
        custo_total=-100.00,
        valor_atual=200.00,
        realizado=0.0,
        latente=100.00,
        mais_menos_valia=100.00,
    )


# ---------------------------------------------------------------------------
# 11. A comissao entra no custo unitario
# ---------------------------------------------------------------------------

def test_comissao_entra_no_custo_unitario(client, session):
    """Compra de 10 por 100,00 mais 5,00 de comissao.

    Premissa da linha 61: `valor_total` ja inclui a comissao, porque e o
    frontend que soma os dois antes de gravar (`Ativos.jsx:138-139`, com sinal
    negativo na compra). Confirmado nos dados: valor_total e igual ao preco
    unitario vezes a quantidade, mais a comissao.

    Calculo a mao:
      abs(-105,00) = 105,00, logo custo_unitario = 105,00 / 10 = 10,50
      custo_base = 10 x 10,50 = 105,00
      custo_total = -105,00  (negativo, D12a)
      valor_atual = round(10 x 20,00, 2) = 200,00
      latente = 200,00 - 105,00 = +95,00
      mais_menos_valia = 0,00 + 95,00 = +95,00

    Nota: `preco_unitario` vale 100,00 / 10 = 10,00 e o campo e ignorado. Se um
    registo real trouxesse `valor_total` sem a comissao, o custo base saía
    errado sem nenhum aviso.
    """
    tipo = semear_tipo(session, "Acoes", tem_unidades=True)
    ativo = semear_ativo(session, "Acoes Q", tipo)
    semear_movimento(session, ativo, TipoMovimento.compra, date(2025, 1, 10),
                     valor_total=-105.00, quantidade=10, comissao=5.00)
    semear_preco(session, ativo, DATA_PRECO, PRECO_UNITARIO)

    resumo = pedir_resumo(client, ativo)

    confirmar_resumo(
        resumo,
        quantidade=10.0,
        custo_total=-105.00,
        valor_atual=200.00,
        realizado=0.0,
        latente=95.00,
        mais_menos_valia=95.00,
    )


# ---------------------------------------------------------------------------
# 12. Sem unidades, duas compras e venda total
# ---------------------------------------------------------------------------

def test_bem_sem_unidades_com_duas_compras_e_venda_total(client, session):
    """Um bem sem unidades comprado em duas partes e depois vendido.

    Calculo a mao (ramo dos bens, `patrimonio_serv.py:29-58`):
      custo_base = 10 000,00 + 5 000,00 = 15 000,00
      a venda desconta o custo acumulado inteiro e zera-o:
        realizado = 18 000,00 - 15 000,00 = +3 000,00
        custo_base = 0,0  e  vendido = verdadeiro
      como `vendido` e verdadeiro, valor_atual = 0,0, mesmo havendo preco
        registado
      custo_total = round(-0,0, 2) = -0,0
      latente = 0,0 - 0,0 = 0,0
      mais_menos_valia = 3 000,00 + 0,0 = +3 000,00
    """
    tipo = semear_tipo(session, "Imovel", tem_unidades=False)
    ativo = semear_ativo(session, "Apartamento", tipo)
    semear_movimento(session, ativo, TipoMovimento.compra, date(2025, 1, 10),
                     valor_total=-10000.00)
    semear_movimento(session, ativo, TipoMovimento.compra, date(2025, 2, 10),
                     valor_total=-5000.00)
    semear_movimento(session, ativo, TipoMovimento.venda, date(2025, 6, 15),
                     valor_total=18000.00)
    semear_preco(session, ativo, DATA_PRECO, 18000.00)

    resumo = pedir_resumo(client, ativo)

    confirmar_resumo(
        resumo,
        quantidade=0.0,
        custo_total=0.0,
        valor_atual=0.0,
        realizado=3000.00,
        latente=0.0,
        mais_menos_valia=3000.00,
    )


# ---------------------------------------------------------------------------
# 13. Sem unidades, venda parcial
# ---------------------------------------------------------------------------

def test_bem_sem_unidades_trata_venda_parcial_como_venda_total(client, session):
    """Vender parte de um bem sem unidades zera a posicao toda.

    Calculo a mao (ramo dos bens, `patrimonio_serv.py:43-47`):
      custo_base = 10 000,00 + 5 000,00 = 15 000,00
      a venda e parcial, mas o codigo nao distingue: desconta o custo
      acumulado inteiro e zera-o
        realizado = 20 000,00 - 15 000,00 = +5 000,00
        custo_base = 0,0  e  vendido = verdadeiro
      como `vendido` e verdadeiro, valor_atual = 0,0, mesmo havendo preco
      custo_total = round(-0,0, 2) = -0,0
      latente = 0,0
      mais_menos_valia = 5 000,00 + 0,0 = +5 000,00

    Sao duas consequencias, ambas silenciosas:
      o ganho foi reconhecido sobre o custo todo, e nao sobre a parte vendida;
      a parte que ficou por vender passou a ter custo zero e valor zero, ou
      seja, desaparece do patrimonio.

    Sem etiqueta de correccao: o Pedro ainda nao decidiu se isto e erro, por isso
    este teste fixa o comportamento actual e nao o desejado. O cenario 12
    mostra o mesmo codigo com uma venda que e mesmo total.

    DEVIDA-TECNICA: D17 (venda parcial no ramo dos bens tratada como venda
    total).
    """
    tipo = semear_tipo(session, "Imovel", tem_unidades=False)
    ativo = semear_ativo(session, "Loja", tipo)
    semear_movimento(session, ativo, TipoMovimento.compra, date(2025, 1, 10),
                     valor_total=-10000.00)
    semear_movimento(session, ativo, TipoMovimento.compra, date(2025, 2, 10),
                     valor_total=-5000.00)
    semear_movimento(session, ativo, TipoMovimento.venda, date(2025, 6, 15),
                     valor_total=20000.00)
    semear_preco(session, ativo, DATA_PRECO, 20000.00)

    resumo = pedir_resumo(client, ativo)

    confirmar_resumo(
        resumo,
        quantidade=0.0,
        custo_total=0.0,
        valor_atual=0.0,
        realizado=5000.00,
        latente=0.0,
        mais_menos_valia=5000.00,
    )


# ---------------------------------------------------------------------------
# 14. Fracoes e a tolerancia de lote esgotado
# ---------------------------------------------------------------------------

def test_fracoes_esgotam_os_lotes_pela_tolerancia(client, session):
    """Vender 0,3 unidades de 0,1 + 0,2 esgota os dois lotes.

    Calculo a mao:
      lote 1: abs(-10,00) / 0,1 = 100,00 por unidade
      lote 2: abs(-40,00) / 0,2 = 200,00 por unidade
      a venda consome 0,1 do lote 1, que fica a zero e sai da lista:
        0,1 x 100,00 = 10,00
      sobram 0,3 - 0,1; em ponto flutuante isto da 0,19999999999999998, e o
      lote 2 tem 0,2, logo consome 0,19999999999999998:
        0,19999999999999998 x 200,00 = 39,99999999999999
      o lote 2 fica com um residuo de cerca de 2,8e-17, que e menor que a
      tolerancia de 1e-9 e portanto tambem sai da lista
      custo_vendido = 10,00 + 39,99999999999999 = 49,99999999999999
      q_efetiva = 0,3 (a tolerancia esvaziou o resto, nada ficou por consumir)
      valor_efetivo = abs(90,00) x (0,3 / 0,3) = 90,00
      realizado = 90,00 - 49,99999999999999 = 40,000000000000014
        o router arredonda: round(40,000000000000014, 2) = 40,00
      lotes vazios: quantidade = 0,0 e custo_base = 0,0
      custo_total = 0,0
      valor_atual = 0,0 (nao ha quantidade)
      latente = 0,0
      mais_menos_valia = 40,00 + 0,0 = +40,00

    E o que impede que um residuo de ponto flutuante deixe um lote fantasma de
    quantidade minuscula, com custo e sem valor.
    """
    tipo = semear_tipo(session, "Crypto", tem_unidades=True)
    ativo = semear_ativo(session, "Bitcoin", tipo)
    semear_movimento(session, ativo, TipoMovimento.compra, date(2025, 1, 10),
                     valor_total=-10.00, quantidade=0.1)
    semear_movimento(session, ativo, TipoMovimento.compra, date(2025, 2, 10),
                     valor_total=-40.00, quantidade=0.2)
    semear_movimento(session, ativo, TipoMovimento.venda, date(2025, 3, 10),
                     valor_total=90.00, quantidade=0.3)
    semear_preco(session, ativo, DATA_PRECO, PRECO_UNITARIO)

    resumo = pedir_resumo(client, ativo)

    confirmar_resumo(
        resumo,
        quantidade=0.0,
        custo_total=0.0,
        valor_atual=0.0,
        realizado=40.00,
        latente=0.0,
        mais_menos_valia=40.00,
    )


# ---------------------------------------------------------------------------
# 15. Duas compras na mesma data
# ---------------------------------------------------------------------------

def test_duas_compras_na_mesma_data_resolvem_pelo_id(client, session):
    """Duas compras no mesmo dia: o FIFO desempata pelo id.

    Calculo a mao (o endpoint ordena por data e depois por id,
    `routers/patrimonio.py:166`, e o `id` segue a ordem de insercao):
      lote 1, id menor, a 10,00: consome 10, logo 10 x 10,00 = 100,00
      lote 2, id maior, a 30,00: consome 5, logo 5 x 30,00 = 150,00
      custo_vendido = 100,00 + 150,00 = 250,00
      valor_efetivo = abs(450,00) x (15 / 15) = 450,00
      realizado = 450,00 - 250,00 = +200,00
      resta o lote 2 com 5 unidades a 30,00: custo_base = 150,00
      custo_total = -150,00  (negativo, D12a)
      valor_atual = round(5 x 20,00, 2) = 100,00
      latente = 100,00 - 150,00 = -50,00
      mais_menos_valia = 200,00 + (-50,00) = +150,00

    O assert do `custo_total` e o que fixa a ordem: se o FIFO pegasse primeiro
    no lote caro, o que restava seriam 5 unidades a 10,00, isto e 50,00 de custo
    e nao 150,00.
    """
    tipo = semear_tipo(session, "Acoes", tem_unidades=True)
    ativo = semear_ativo(session, "Acoes P", tipo)
    semear_movimento(session, ativo, TipoMovimento.compra, date(2025, 1, 10),
                     valor_total=-100.00, quantidade=10)
    semear_movimento(session, ativo, TipoMovimento.compra, date(2025, 1, 10),
                     valor_total=-300.00, quantidade=10)
    semear_movimento(session, ativo, TipoMovimento.venda, date(2025, 2, 10),
                     valor_total=450.00, quantidade=15)
    semear_preco(session, ativo, DATA_PRECO, PRECO_UNITARIO)

    resumo = pedir_resumo(client, ativo)

    confirmar_resumo(
        resumo,
        quantidade=5.0,
        custo_total=-150.00,
        valor_atual=100.00,
        realizado=200.00,
        latente=-50.00,
        mais_menos_valia=150.00,
    )


# ---------------------------------------------------------------------------
# 16. Venda com quantidade zero
# ---------------------------------------------------------------------------

def test_venda_com_quantidade_zero_e_ignorada(client, session):
    """Uma venda de 0 unidades nao entra no calculo.

    Calculo a mao: a venda e descartada antes de calcular o custo
    (`patrimonio_serv.py:75`), por isso o FIFO nao se mexe e o resultado e o do
    cenario 1:
      custo_base = 10 x 10,00 = 100,00
      custo_total = -100,00  (negativo, D12a)
      valor_atual = round(10 x 20,00, 2) = 200,00
      latente = 200,00 - 100,00 = +100,00
      realizado = 0,00
      mais_menos_valia = 0,00 + 100,00 = +100,00

    Os 50,00 de encaixe do movimento somem sem erro e sem registo, tal como
    acontece na sobre-venda, mas por outra raza: aqui a quantidade e mesmo
    zero.
    """
    tipo = semear_tipo(session, "Acoes", tem_unidades=True)
    ativo = semear_ativo(session, "Acoes O", tipo)
    semear_movimento(session, ativo, TipoMovimento.compra, date(2025, 1, 10),
                     valor_total=-100.00, quantidade=10)
    semear_movimento(session, ativo, TipoMovimento.venda, date(2025, 4, 10),
                     valor_total=50.00, quantidade=0)
    semear_preco(session, ativo, DATA_PRECO, PRECO_UNITARIO)

    resumo = pedir_resumo(client, ativo)

    confirmar_resumo(
        resumo,
        quantidade=10.0,
        custo_total=-100.00,
        valor_atual=200.00,
        realizado=0.0,
        latente=100.00,
        mais_menos_valia=100.00,
    )


# ---------------------------------------------------------------------------
# 17. Bem sem unidades e sem preco
# ---------------------------------------------------------------------------

def test_bem_sem_unidades_e_sem_preco_desaparece_do_patrimonio(client, session):
    """Um bem sem preco vale zero, mesmo tendo 15 000,00 de custo.

    Calculo a mao (ramo dos bens, `patrimonio_serv.py:53-56`):
      custo_base = abs(-15000,00) = 15 000,00
      nao houve venda e o custo e positivo, mas sem preco o valor e 0,0
      custo_total = -15 000,00  (negativo, D12a)
      valor_atual = 0,0
      latente = None, porque `preco_atual` e None
      mais_menos_valia = round(0,00 + 0,0, 2) = 0,00
      quantidade = 0,0

    Os 15 000,00 de custo ficam visiveis no `custo_total` e nao aparecem em mais
    nada: o bem vale zero, o latente e nulo e o mais/menos-valia e zero. Na
    pratica, um bem sem registo de preco desaparece do patrimonio.

    DEVIDA-TECNICA: D16 (bem sem preco desaparece do patrimonio).
    """
    tipo = semear_tipo(session, "Imovel", tem_unidades=False)
    ativo = semear_ativo(session, "Terreno", tipo)
    semear_movimento(session, ativo, TipoMovimento.compra, date(2025, 1, 10),
                     valor_total=-15000.00)

    resumo = pedir_resumo(client, ativo)

    confirmar_resumo(
        resumo,
        quantidade=0.0,
        custo_total=-15000.00,
        valor_atual=0.0,
        realizado=0.0,
        latente=None,
        mais_menos_valia=0.0,
    )
    assert resumo["preco_atual"] is None


# ---------------------------------------------------------------------------
# 18. Fracções: a tolerância tem de esgotar os lotes até zero
# ---------------------------------------------------------------------------

def test_fraccoes_esgotam_os_lotes_sem_deixar_residuo(session):
    """0,1 + 0,2 vendidas em 0,3: não pode ficar resíduo de nenhuma das duas.

    Este é o único teste do ficheiro que não entra pelo endpoint. A razão está
    no arredondamento: o router devolve `round(quantidade, 6)` e
    `round(-custo_base, 2)` (`routers/patrimonio.py:197-198`), e o resíduo que
    fica quando a tolerância é removida é de 2,78e-17. Qualquer arredondamento
    o transforma em 0,0, pelo que pelo endpoint o comportamento errado e o certo
    são indistinguíveis. Afirma-se o valor bruto da função.

    Cálculo à mão (ramo das unidades, `patrimonio_serv.py:60-100`):
      compras: abs(-1,00) / 0,1 = 10,00 e abs(-4,00) / 0,2 = 20,00 por unidade
      venda de 0,3 consome 0,1 do primeiro lote e 0,2 do segundo
        0,1 - 0,1 = 0,0  -> lote esgotado e removido
        0,2 - 0,2 = 0,0  -> lote esgotado e removido
      em vírgula flutuante a subtração acima dá 2,78e-17, e a tolerância de 1e-9
      das linhas 80 e 86 é a que a deita fora
      custo vendido = 0,1 x 10,00 + 0,2 x 20,00 = 5,00
      valor efetivo  = abs(6,00) x (0,3 / 0,3)   = 6,00
      realizado      = 6,00 - 5,00 = +1,00
      sem lotes, a soma das quantidades e a soma dos custos dão 0
        quantidade = 0  e  custo_base = 0

    Note-se que `quantidade` e `custo_base` são somas de uma lista vazia, e por
    isso vêm como o inteiro 0. `0 == 0.0` é verdadeiro, por isso as constantes
    estão escritas como 0.0 e a comparação é a mesma que se fizesse com o
    inteiro.
    """
    tipo = semear_tipo(session, "Acoes", tem_unidades=True)
    ativo = semear_ativo(session, "Acoes Fraccionadas", tipo)
    semear_movimento(session, ativo, TipoMovimento.compra, date(2025, 1, 10),
                     valor_total=-1.00, quantidade=0.1)
    semear_movimento(session, ativo, TipoMovimento.compra, date(2025, 2, 10),
                     valor_total=-4.00, quantidade=0.2)
    semear_movimento(session, ativo, TipoMovimento.venda, date(2025, 3, 10),
                     valor_total=6.00, quantidade=0.3)
    preco = semear_preco(session, ativo, DATA_PRECO, PRECO_UNITARIO)

    movimentos = (
        session.query(MovimentoAtivo)
        .filter(MovimentoAtivo.ativo_id == ativo.id)
        .order_by(MovimentoAtivo.data, MovimentoAtivo.id)
        .all()
    )

    resultado = _resumo_valor_ativo(ativo, movimentos, preco)

    assert resultado["quantidade"] == 0.0, (
        f"quantidade: esperado 0,0, veio {resultado['quantidade']!r}"
    )
    assert resultado["custo_base"] == 0.0, (
        f"custo_base: esperado 0,0, veio {resultado['custo_base']!r}"
    )
    assert resultado["realizado"] == 1.0, (
        f"realizado: esperado 1,0, veio {resultado['realizado']!r}"
    )


# ---------------------------------------------------------------------------
# 19. Três lotes: a ordem de consumo não se deduz do mais/menos-valia
# ---------------------------------------------------------------------------

def test_tres_lotes_consomem_do_mais_antigo_para_o_mais_recente(client, session):
    """Vender 15 unidades com três lotes em carteira, a saída depende da ordem.

    Cálculo à mão (ramo das unidades, `patrimonio_serv.py:60-100`), por FIFO:
      compras: abs(-100,00) / 10 = 10,00
               abs(-200,00) / 10 = 20,00
               abs(-300,00) / 10 = 30,00
      venda de 15 por 450 consome o lote mais antigo primeiro
        primeiro lote: 10 x 10,00 = 100,00  e fica a 0
        segundo lote:  5 x 20,00 = 100,00  e sobram 5
        custo vendido = 100,00 + 100,00 = 200,00
        q_efetiva = 15, logo valor efetivo = 450,00
        realizado = 450,00 - 200,00 = +250,00
      posição que fica
        quantidade = 5 + 10 = 15
        custo_base = 5 x 20,00 + 10 x 30,00 = 100,00 + 300,00 = 400,00
        custo_total = -400,00  (negativo, D12a)
        valor_atual = round(15 x 20,00, 2) = 300,00
        latente = 300,00 - 400,00 = -100,00
        mais_menos_valia = 250,00 - 100,00 = +150,00

    Por que este cenário e não um de dois lotes: com dois lotes e uma venda que os
    atravessa a ambos, o mais/menos-valia dá o mesmo nos dois sentidos, porque a
    soma de dois produtos comutativos é a mesma. Invertendo a ordem, o mesmo
    conjunto de números produziria

        custo vendido = 10 x 30,00 + 5 x 20,00 = 400,00
        realizado     = 450,00 - 400,00 = +50,00
        posição       = 10 x 10,00 + 5 x 20,00 = 200,00  -> custo_total = -200,00
        latente       = 300,00 - 200,00 = +100,00
        mais_menos_valia = 50,00 + 100,00 = +150,00

    O mais/menos-valia é +150,00 nos dois casos, por isso não serve para
    distinguir. É o `realizado` e o `custo_total` que distinguem: +250,00 contra
    +50,00, e -400,00 contra -200,00. São eles que fixam a ordem de consumo.
    """
    tipo = semear_tipo(session, "Acoes", tem_unidades=True)
    ativo = semear_ativo(session, "Acoes Tres Lotes", tipo)
    semear_movimento(session, ativo, TipoMovimento.compra, date(2025, 1, 10),
                     valor_total=-100.00, quantidade=10)
    semear_movimento(session, ativo, TipoMovimento.compra, date(2025, 2, 10),
                     valor_total=-200.00, quantidade=10)
    semear_movimento(session, ativo, TipoMovimento.compra, date(2025, 3, 10),
                     valor_total=-300.00, quantidade=10)
    semear_movimento(session, ativo, TipoMovimento.venda, date(2025, 6, 10),
                     valor_total=450.00, quantidade=15)
    semear_preco(session, ativo, DATA_PRECO, PRECO_UNITARIO)

    resumo = pedir_resumo(client, ativo)

    confirmar_resumo(
        resumo,
        quantidade=15.0,
        custo_total=-400.00,
        valor_atual=300.00,
        realizado=250.00,
        latente=-100.00,
        mais_menos_valia=150.00,
    )
