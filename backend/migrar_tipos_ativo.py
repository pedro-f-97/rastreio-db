"""
Migração: TipoAtivo de enum fixo para tabela configurável.
Cria 'tipos_ativo', faz seed standard, e migra Ativo.tipo -> Ativo.tipo_id.
"""
from sqlalchemy import text
from database import engine, SessionLocal, Base, TipoAtivo

# Mapeamento do enum antigo para o nome do novo tipo
MAPA_ENUM_ANTIGO = {
    "etf": "ETF",
    "crypto": "Crypto",
    "veiculo": "Veículo",
    "imovel": "Imóvel",
    "outro": "Outro",
}

# Seed standard (nome, tem_unidades)
SEED_TIPOS = [
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


def migrar():
    db = SessionLocal()
    conn = engine.connect()
    trans = conn.begin()

    try:
        # 1. Cria a tabela tipos_ativo (se ainda não existir)
        TipoAtivo.__table__.create(bind=conn, checkfirst=True)

        # 2. Seed dos tipos standard
        ids_por_nome = {}
        for nome, tem_unidades in SEED_TIPOS:
            existente = conn.execute(
                text("SELECT id FROM tipos_ativo WHERE nome = :nome"),
                {"nome": nome},
            ).first()
            if existente:
                ids_por_nome[nome] = existente[0]
                continue
            resultado = conn.execute(
                text("INSERT INTO tipos_ativo (nome, tem_unidades) VALUES (:nome, :tem_unidades)"),
                {"nome": nome, "tem_unidades": tem_unidades},
            )
            ids_por_nome[nome] = resultado.lastrowid

        print(f"✅ Tipos de ativo semeados: {ids_por_nome}")

        # 3. Lê os ativos existentes (schema antigo, coluna 'tipo' como string do enum)
        ativos_existentes = conn.execute(text("SELECT * FROM ativos")).mappings().all()
        print(f"ℹ️  {len(ativos_existentes)} ativos a migrar.")

        # 4. Renomeia a tabela antiga
        conn.execute(text("ALTER TABLE ativos RENAME TO ativos_old"))

        # 5. Cria a tabela 'ativos' nova, com o schema atual do models.py (tipo_id em vez de tipo)
        from database import Ativo
        Ativo.__table__.create(bind=conn, checkfirst=True)

        # 6. Copia os dados, traduzindo tipo -> tipo_id, preservando os IDs originais
        for ativo in ativos_existentes:
            nome_tipo_novo = MAPA_ENUM_ANTIGO.get(ativo["tipo"])
            if nome_tipo_novo is None:
                raise ValueError(f"Tipo de ativo desconhecido no registo antigo: {ativo['tipo']!r}")
            tipo_id = ids_por_nome[nome_tipo_novo]

            conn.execute(
                text("""
                    INSERT INTO ativos (id, nome, tipo_id, simbolo, moeda, notas, contabilizacao)
                    VALUES (:id, :nome, :tipo_id, :simbolo, :moeda, :notas, :contabilizacao)
                """),
                {
                    "id": ativo["id"],
                    "nome": ativo["nome"],
                    "tipo_id": tipo_id,
                    "simbolo": ativo["simbolo"],
                    "moeda": ativo["moeda"],
                    "notas": ativo["notas"],
                    "contabilizacao": ativo["contabilizacao"],
                },
            )

        # 7. Apaga a tabela antiga
        conn.execute(text("DROP TABLE ativos_old"))

        trans.commit()
        print("✅ Migração concluída com sucesso.")

    except Exception as e:
        trans.rollback()
        print(f"❌ Erro na migração, rollback efetuado: {e}")
        raise
    finally:
        conn.close()
        db.close()


if __name__ == "__main__":
    migrar()