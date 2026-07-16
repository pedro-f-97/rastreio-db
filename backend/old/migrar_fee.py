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

    cur.execute("PRAGMA table_info(perfis_importacao)")
    colunas = [row[1] for row in cur.fetchall()]

    if "coluna_fee" not in colunas:
        cur.execute("ALTER TABLE perfis_importacao ADD COLUMN coluna_fee INTEGER")
        print("✅ Coluna coluna_fee adicionada a perfis_importacao.")
    else:
        print("ℹ️  coluna_fee já existe em perfis_importacao.")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    migrar()