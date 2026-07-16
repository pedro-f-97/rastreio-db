import sqlite3
import os
import sys

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.path.join(BASE_DIR, "dados", "rastreio.db")

def migrar():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Verifica se a coluna já existe antes de adicionar
    cur.execute("PRAGMA table_info(subcategorias)")
    colunas = [row[1] for row in cur.fetchall()]

    if "trata_patrimonio" not in colunas:
        cur.execute("ALTER TABLE subcategorias ADD COLUMN trata_patrimonio BOOLEAN DEFAULT 0")
        print("✅ Coluna trata_patrimonio adicionada a subcategorias.")
    else:
        print("ℹ️  Coluna trata_patrimonio já existe — nada a fazer.")

    conn.commit()
    conn.close()

    # As tabelas novas (ativos, movimentos_ativo, precos_ativo) são criadas pelo create_all
    from database import criar_tabelas
    criar_tabelas()
    print("✅ Tabelas novas criadas (se não existiam).")

if __name__ == "__main__":
    migrar()