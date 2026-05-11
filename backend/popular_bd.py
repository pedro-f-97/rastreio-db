from database import SessionLocal, Categoria, Subcategoria, criar_tabelas, TipoCategoria

CATEGORIAS = {
    "Receita": ["Salário", "IRS", "Transferência de Poupanças"],
    "Entretenimento": ["Lazer", "Jogos", "Cinema", "Viagens", "Subscrições", "Restauração", "Hardware", "Diversos"],
    "Transporte": ["Combustível", "Portagens", "Seguro", "Manutenção", "Carro", "IUC", "Inspeção"],
    "Saúde": ["Consultas", "Farmácia", "Outros"],
    "Casa": ["Renda", "Manutenção", "Compras", "Supermercado"],
    "Aparência": ["Roupa", "Cabeleireiro"],
    "Investimento": ["ETFs", "Crypto", "Poupança"],
    "Pontual": ["Jurídico", "Outros"],
    "Prendas": ["Família", "Namorada"],
}

TIPOS = {
    "Receita": TipoCategoria.receita,
    "Investimento": TipoCategoria.investimento,
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
        for nome_sub in subcategorias:
            sub = Subcategoria(nome=nome_sub, categoria_id=cat.id)
            session.add(sub)

    session.commit()
    session.close()
    print("Categorias e subcategorias criadas com sucesso!")

if __name__ == "__main__":
    popular()