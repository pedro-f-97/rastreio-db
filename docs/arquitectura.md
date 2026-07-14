# Arquitetura

```
rastreio-db/
    ├── README.md
    ├── DEV.md
    ├── WINDOWS.md
    ├── LICENSE
    ├── build.sh                        # Script de build Linux
    ├── build.bat                       # Script de build Windows
    ├── docs/
    │   └── screenshots/
    ├── backend/
    │   ├── main.py                     # Ponto de entrada FastAPI + CORS
    │   ├── database.py                 # Modelos SQLAlchemy e ligação à BD
    │   ├── schemas.py                  # Schemas Pydantic para validação de dados
    │   ├── parser_importacao.py        # Parser reutilizável de ficheiros Excel e CSV
    │   ├── importador_transacoes.py    # Inserção de transações com deduplicação e regras
    │   ├── popular_bd.py               # Categorias e subcategorias predefinidas
    │   ├── tray.py                     # Janela de controlo (abrir browser / encerrar)
    │   ├── requirements.txt
    │   ├── migrar_adicionar_transferencia.py
    │   ├── migrar_contas.py
    │   ├── migrar_excel.py
    │   ├── migrar_fee.py
    │   ├── migrar_patrimonio.py
    │   ├── migrar_regras_categoria_opcional.py
    │   ├── migrar_tipo_categoria.py
    │   └── routers/
    │       ├── __init__.py
    │       ├── backups.py              # Exportação e restauro da base de dados
    │       ├── categorias.py           # CRUD de categorias e subcategorias
    │       ├── configuracao.py         # Inicialização e estado da aplicação
    │       ├── contas.py               # CRUD de contas bancárias
    │       ├── estatisticas.py         # Endpoints de estatísticas e resumos
    │       ├── importacao.py           # Preview e importação de extratos bancários
    │       ├── patrimonio.py           # Gestão de activos e movimentos patrimoniais
    │       ├── perfis_importacao.py    # CRUD de perfis de mapeamento por banco
    │       ├── regras.py               # Regras de categorização automática
    │       └── transacoes.py           # Listagem paginada e edição de transações
    └── frontend/
        ├── index.html
        ├── vite.config.js
        ├── package.json
        ├── eslint.config.js
        ├── public/
        │   └── favicon.ico             # Ícone para o projecto
        └── src/
            ├── index.css
            ├── main.jsx
            ├── App.jsx
            ├── App.css
            ├── assets/
            │   ├── nariz.svg            # Logótipo do projecto
            │   └── fonts/
            ├── utils/
            │   └── formatacao.js
            ├── contexts/
            │   └── GuiaContext.jsx      # Estado do tour guiado (iniciar/avançar/sair/reiniciar)
            ├── api/
            │   ├── client.js
            │   ├── backups.js
            │   ├── categorias.js
            │   ├── configuracao.js
            │   ├── contas.js
            │   ├── estatisticas.js
            │   ├── importacao.js
            │   ├── patrimonio.js
            │   ├── perfisImportacao.js
            │   ├── regras.js
            │   └── transacoes.js
            ├── components/
            │   ├── FiltrosTransacoes.jsx
            │   ├── TabelaTransacoes.jsx
            │   └── GuiaDestaque.jsx + .css   # Highlight de elementos durante o tour guiado
            └── pages/
                ├── Categorias.jsx + .css
                ├── Contas.jsx + .css
                ├── Estatisticas.jsx + .css
                ├── Historico.jsx
                ├── Importacao.jsx + .css
                ├── Patrimonio.jsx + .css
                ├── PrimeiroUso.jsx
                ├── Regras.jsx + .css
                ├── Sobre.jsx + .css        # Página "Conceitos" — explicação das áreas da app
                └── Transacoes.jsx + .css
```