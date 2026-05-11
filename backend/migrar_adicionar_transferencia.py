from database import SessionLocal, Categoria, Subcategoria, TipoCategoria

db = SessionLocal()

cat = Categoria(nome="Transferência", tipo=TipoCategoria.transferencia)
db.add(cat)
db.flush()

for nome_sub in ["Poupanças"]:
    sub = Subcategoria(nome=nome_sub, categoria_id=cat.id)
    db.add(sub)

db.commit()
db.close()

print("Categoria Transferência criada.")