from enum import Enum

from sqlalchemy.orm import Session

from database import Categoria, Subcategoria, TipoAtivo, TipoCategoria


class PerfilCategorias(str, Enum):
    minimalista = "minimalista"
    completo = "completo"


CATEGORIAS_MINIMALISTA = {
    "Receita": [
        ("Salário", False),
        ("Venda", False),
        ("Outros", False),
    ],
    "Casa": [
        ("Prestação", True),
        ("Renda", False),
        ("Condomínio", False),
        ("Outros", False),
    ],
    "Transporte": [
        ("Combustível", False),
        ("Outros", False),
    ],
    "Saúde": [
        ("Outros", False),
    ],
    "Lazer": [
        ("Outros", False),
    ],
    "Investimento": [
        ("Outros", True),
    ],
    "Transferência": [
        ("Conta Principal → Poupanças", False),
        ("Poupanças → Conta Principal", False),
    ],
    "Diversos": [
        ("Outros", False),
    ],
}

CATEGORIAS_COMPLETO = {
    "Receita": [
        ("Salário", False),
        ("Venda", False),
        ("Outros", False),
    ],
    "Casa": [
        ("Renda", False),
        ("Prestação", True),
        ("Condomínio", False),
        ("Manutenção", True),
        ("Equipamentos", False),
        ("Supermercado", False),
        ("Luz", False),
        ("Água", False),
        ("Outros", False),
    ],
    "Transporte": [
        ("Combustível", False),
        ("Transportes públicos", False),
        ("Portagens", False),
        ("Seguro", False),
        ("Manutenção", False),
        ("IUC", False),
        ("Inspeção", False),
        ("Outros", False),
    ],
    "Saúde": [
        ("Seguro de saúde", False),
        ("Consultas", False),
        ("Farmácia", False),
        ("Outros", False),
    ],
    "Cuidados Pessoais": [
        ("Roupa", False),
        ("Cabeleireiro", False),
        ("Outros", False),
    ],
    "Lazer": [
        ("Cinema", False),
        ("Viagens", False),
        ("Subscrições", False),
        ("Restauração", False),
        ("Outros", False),
    ],
    "Investimento": [
        ("Ações", True),
        ("ETFs", True),
        ("Obrigações", True),
        ("Fundos", True),
        ("Criptoativos", True),
        ("Outros", True),
    ],
    "Prendas": [
        ("Família", False),
        ("Amigos", False),
    ],
    "Transferência": [
        ("Conta Principal → Poupanças", False),
        ("Poupanças → Conta Principal", False),
    ],
    "Património": [
        ("Imóveis", True),
        ("Veículos", True),
        ("Outros ativos", True),
    ],
    "Educação": [
        ("Livros", False),
        ("Cursos", False),
    ],
    "Serviços": [
        ("Internet", False),
        ("Streaming", False),
        ("Outros", False),
    ],
    "Animais": [
        ("Outros", False),
    ],
    "Taxas e Impostos": [
        ("Outros", False),
    ],
    "Diversos": [
        ("Outros", False),
    ],
}

TIPOS = {
    "Receita": TipoCategoria.receita,
    "Investimento": TipoCategoria.investimento,
    "Transferência": TipoCategoria.transferencia,
    "Património": TipoCategoria.despesa,
}

SEED_TIPOS_ATIVO = [
    ("ETF", True),
    ("Ações", True),
    ("Crypto", True),
    ("Ouro", True),
    ("Obrigações", True),
    ("Certificados de Aforro", True),  # subscritos em unidades (D12f)
    ("Veículo", False),
    ("Imóvel", False),
    ("Outro", False),
]

def semear_dados_iniciais(db: Session, perfil: PerfilCategorias, com_categorias: bool) -> None:
    """Cria, pelo nome, só o que falta das listas iniciais (D12g, D25).

    O que já existe não é tocado, pelo que pode correr sobre uma BD com dados
    sem dar erro de nome duplicado. Não faz commit: quem chama decide.
    """
    if com_categorias:
        categorias = (
            CATEGORIAS_MINIMALISTA if perfil == PerfilCategorias.minimalista else CATEGORIAS_COMPLETO
        )
        existentes = {c.nome: c for c in db.query(Categoria).all()}
        for nome_cat, subcategorias in categorias.items():
            cat = existentes.get(nome_cat)
            if cat is None:
                cat = Categoria(nome=nome_cat, tipo=TIPOS.get(nome_cat, TipoCategoria.despesa))
                db.add(cat)
                db.flush()
            nomes_sub = {s.nome for s in cat.subcategorias}
            for nome_sub, trata_patrimonio in subcategorias:
                if nome_sub not in nomes_sub:
                    db.add(Subcategoria(nome=nome_sub, categoria_id=cat.id, trata_patrimonio=trata_patrimonio))
                    nomes_sub.add(nome_sub)

    tipos_existentes = {t.nome for t in db.query(TipoAtivo).all()}
    for nome, tem_unidades in SEED_TIPOS_ATIVO:
        if nome not in tipos_existentes:
            db.add(TipoAtivo(nome=nome, tem_unidades=tem_unidades))
