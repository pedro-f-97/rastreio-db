from database import SessionLocal
from sqlalchemy import text

db = SessionLocal()

db.execute(text("PRAGMA foreign_keys = OFF"))

db.execute(text("""
    CREATE TABLE regras_categorizacao_new (
        id INTEGER PRIMARY KEY,
        palavra_chave VARCHAR(100) NOT NULL UNIQUE,
        categoria_id INTEGER REFERENCES categorias(id),
        subcategoria_id INTEGER REFERENCES subcategorias(id)
    )
"""))

db.execute(text("""
    INSERT INTO regras_categorizacao_new (id, palavra_chave, categoria_id, subcategoria_id)
    SELECT id, palavra_chave, categoria_id, subcategoria_id FROM regras_categorizacao
"""))

db.execute(text("DROP TABLE regras_categorizacao"))
db.execute(text("ALTER TABLE regras_categorizacao_new RENAME TO regras_categorizacao"))

db.commit()
db.execute(text("PRAGMA foreign_keys = ON"))
db.close()

print("Migração concluída.")