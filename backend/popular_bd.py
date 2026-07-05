from database import SessionLocal, Categoria, Subcategoria, criar_tabelas, TipoCategoria

CATEGORIAS = {
    "Receita": [
        ("Salário", False),
        ("IRS", False),
        ("Vendas", False),
    ],
    "Entretenimento": [
        ("Cinema", False),
        ("Viagens", False),
        ("Subscrições", False),
        ("Restauração", False),
        ("Diversos", False),
    ],
    "Transporte": [
        ("Combustível", False),
        ("Portagens", False),
        ("Seguro", False),
        ("Manutenção", False),
        ("IUC", False),
        ("Inspeção", False),
    ],
    "Saúde": [
        ("Consultas", False),
        ("Farmácia", False),
        ("Outros", False),
    ],
    "Casa": [
        ("Renda", False),
        ("Manutenção", False),
        ("Equipamentos", False),
        ("Supermercado", False),
        ("Luz", False),
        ("Água", False),
    ],
    "Aparência": [
        ("Roupa", False),
        ("Cabeleireiro", False),
    ],
    "Investimento": [
        ("ETFs", True),
        ("Crypto", True),
    ],
    "Prendas": [
        ("Família", False),
        ("Amigos", False),
    ],
    "Transferência": [
        ("Para Conta A", False),
        ("Para Conta B", False),
    ],
    "Património": [
        ("Automóvel", True),
        ("Habitação", True),
    ],
}

TIPOS = {
    "Receita": TipoCategoria.receita,
    "Investimento": TipoCategoria.investimento,
    "Transferência": TipoCategoria.transferencia,
    "Património": TipoCategoria.despesa,
}


def popular():
    session = SessionLocal()

    if session.query(Categoria).count() > 0:
        print("A base de dados já tem categorias. Popular cancelado.")
        session.close()
        return

    for nome_cat, subcategorias in CATEGORIAS.items():
        cat = Categoria(nome=nome_cat, tipo=TIPOS.get(nome_cat, TipoCategoria.despesa))
        session.add(cat)
        session.flush()
        for nome_sub, trata_patrimonio in subcategorias:
            sub = Subcategoria(nome=nome_sub, categoria_id=cat.id, trata_patrimonio=trata_patrimonio)
            session.add(sub)

    session.commit()
    session.close()
    print("Categorias e subcategorias criadas com sucesso!")


if __name__ == "__main__":
    popular()