from database import SessionLocal, Categoria, TipoCategoria
from sqlalchemy import text

db = SessionLocal()

# Adiciona a coluna se não existir
db.execute(text("ALTER TABLE categorias ADD COLUMN tipo VARCHAR NOT NULL DEFAULT 'despesa'"))
db.commit()

# Mapeia nomes conhecidos para o tipo correcto
mapa = {
    "Receita": TipoCategoria.receita,
    "Investimento": TipoCategoria.investimento,
}

categorias = db.query(Categoria).all()
for cat in categorias:
    cat.tipo = mapa.get(cat.nome, TipoCategoria.despesa)

db.commit()
db.close()

print("Migração concluída.")