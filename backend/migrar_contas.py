import sqlite3
import os
import sys
from datetime import date

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.path.join(BASE_DIR, "dados", "rastreio.db")

def migrar():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Cria tabela contas
    cur.execute("""
        CREATE TABLE IF NOT EXISTS contas (
            id INTEGER PRIMARY KEY,
            nome TEXT NOT NULL UNIQUE,
            saldo_referencia REAL NOT NULL DEFAULT 0,
            data_referencia TEXT NOT NULL,
            ativa INTEGER NOT NULL DEFAULT 1
        )
    """)

    # Adiciona conta_id a transacoes se não existir
    cur.execute("PRAGMA table_info(transacoes)")
    colunas = [row[1] for row in cur.fetchall()]
    if "conta_id" not in colunas:
        cur.execute("ALTER TABLE transacoes ADD COLUMN conta_id INTEGER REFERENCES contas(id)")
        print("✅ Coluna conta_id adicionada a transacoes.")
    else:
        print("ℹ️  conta_id já existe em transacoes.")

    # Adiciona conta_id a perfis_importacao se não existir
    cur.execute("PRAGMA table_info(perfis_importacao)")
    colunas = [row[1] for row in cur.fetchall()]
    if "conta_id" not in colunas:
        cur.execute("ALTER TABLE perfis_importacao ADD COLUMN conta_id INTEGER REFERENCES contas(id)")
        print("✅ Coluna conta_id adicionada a perfis_importacao.")
    else:
        print("ℹ️  conta_id já existe em perfis_importacao.")

    # Cria conta ActivoBank se não existir
    cur.execute("SELECT id FROM contas WHERE nome = 'ActivoBank'")
    conta = cur.fetchone()
    if not conta:
        # Data mais antiga das transacções existentes
        cur.execute("SELECT MIN(data) FROM transacoes")
        data_min = cur.fetchone()[0] or str(date.today())
        cur.execute(
            "INSERT INTO contas (nome, saldo_referencia, data_referencia, ativa) VALUES (?, ?, ?, 1)",
            ("ActivoBank", 0.0, data_min)
        )
        conta_id = cur.lastrowid
        print(f"✅ Conta ActivoBank criada (id={conta_id}, data_referencia={data_min}).")
    else:
        conta_id = conta[0]
        print(f"ℹ️  Conta ActivoBank já existe (id={conta_id}).")

    # Atribui todas as transacções sem conta à ActivoBank
    cur.execute("UPDATE transacoes SET conta_id = ? WHERE conta_id IS NULL", (conta_id,))
    print(f"✅ {cur.rowcount} transacções atribuídas à ActivoBank.")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    migrar()