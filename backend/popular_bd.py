from enum import Enum
from database import SessionLocal, Categoria, Subcategoria, criar_tabelas, TipoCategoria


class PerfilCategorias(str, Enum):
    minimalista = "minimalista"
    completo = "completo"


CATEGORIAS_MINIMALISTA = {
    "Receita": [
        ("Salário", False),
        ("Reembolso", False),
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
        ("Reembolso", False),
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
    ("Certificados de Aforro", False),
    ("Veículo", False),
    ("Imóvel", False),
    ("Outro", False),
]

def popular(perfil: PerfilCategorias = PerfilCategorias.completo):
    categorias = (
        CATEGORIAS_MINIMALISTA if perfil == PerfilCategorias.minimalista else CATEGORIAS_COMPLETO
    )

    session = SessionLocal()

    if session.query(Categoria).count() > 0:
        print("A base de dados já tem categorias. Popular cancelado.")
        session.close()
        return

    for nome_cat, subcategorias in categorias.items():
        cat = Categoria(nome=nome_cat, tipo=TIPOS.get(nome_cat, TipoCategoria.despesa))
        session.add(cat)
        session.flush()
        for nome_sub, trata_patrimonio in subcategorias:
            sub = Subcategoria(nome=nome_sub, categoria_id=cat.id, trata_patrimonio=trata_patrimonio)
            session.add(sub)

    session.commit()
    session.close()
    print(f"Categorias e subcategorias criadas com sucesso! (perfil: {perfil.value})")


def _perfil_via_input() -> PerfilCategorias:
    resposta = input("Perfil de categorias [minimalista/completo] (default: completo): ").strip().lower()
    if resposta == "minimalista":
        return PerfilCategorias.minimalista
    return PerfilCategorias.completo


if __name__ == "__main__":
    popular(_perfil_via_input())