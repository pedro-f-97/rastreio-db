# rastreio-db

Tracker pessoal de despesas bancárias, desenvolvido como projecto de portfolio.

## Tecnologias

- **Backend:** Python 3.14 + FastAPI + SQLAlchemy + SQLite
- **Frontend:** React + Vite
- **Servidor:** Uvicorn

## Arquitectura
rastreio-db/
├── .gitignore
├── README.md
├── backend/
│   ├── database.py          # Modelos SQLAlchemy e ligação à BD
│   ├── main.py              # Ponto de entrada FastAPI + CORS
│   ├── popular_bd.py        # Popula BD com categorias e subcategorias
│   ├── migrar_excel.py      # Migração única de dados históricos
│   ├── requirements.txt
│   └── routers/
│       ├── categorias.py    # CRUD de categorias e subcategorias
│       ├── transacoes.py    # Listagem paginada e edição de transações
│       ├── regras.py        # Regras de categorização automática
│       ├── importacao.py    # Importação de extratos Excel do banco
│       └── estatisticas.py  # Endpoints de estatísticas e resumos
└── frontend/
└── src/
├── api/
│   ├── client.js        # Cliente axios centralizado
│   ├── transacoes.js    # Chamadas ao endpoint de transações
│   ├── categorias.js    # Chamadas ao endpoint de categorias
│   ├── regras.js        # Chamadas ao endpoint de regras
│   └── estatisticas.js  # Chamadas ao endpoint de estatísticas
├── components/
│   ├── TabelaTransacoes.jsx
│   └── FiltrosTransacoes.jsx
└── pages/
├── Transacoes.jsx
├── Transacoes.css
├── Categorias.jsx
├── Categorias.css
├── Regras.jsx
├── Regras.css
├── Estatisticas.jsx
└── Estatisticas.css

## Modelo de dados

- **Categoria** — categorias de despesa (Casa, Transporte, Saúde, etc.)
- **Subcategoria** — subdivisão de cada categoria (Supermercado, Combustível, etc.)
- **Transacao** — registo de cada movimento bancário, com categoria, subcategoria, flag de reembolso e notas
- **RegraCategorizacao** — regras por palavra-chave para categorização automática na importação

## Categorias

| Categoria | Subcategorias |
|---|---|
| Receita | Salário, IRS, Transferência de Poupanças |
| Entretenimento | Lazer, Jogos, Cinema, Viagens, Subscrições, Restauração, Hardware, Diversos |
| Transporte | Combustível, Portagens, Seguro, Manutenção, Carro, IUC, Inspeção |
| Saúde | Consultas, Farmácia, Outros |
| Casa | Renda, Manutenção, Compras, Supermercado |
| Aparência | Roupa, Cabeleireiro |
| Investimento | ETFs, Crypto, Poupança |
| Pontual | Jurídico |
| Prendas | Família, Namorada |

## Funcionalidades

- Importação de extratos Excel exportados do banco
- Deteção automática de duplicados por `data + descrição + valor + saldo`
- Categorização automática por regras de palavra-chave
- Transações com descrição iniciada por `TRF` são sempre manuais — o contexto varia (renda, partilha de despesa, etc.) e não devem ser categorizadas automaticamente
- Sugestão de criação de regra ao categorizar manualmente uma transação
- Edição inline de categoria, subcategoria, reembolso e notas directamente na tabela
- Paginação e filtros por ano, mês e categoria
- Filtro rápido de transações por categorizar
- Aplicação de regras em massa com resolução individual de conflitos
- Estatísticas com resumo mensal, evolução gráfica e análise por categoria
- Interface web com dark mode

## Estado actual

- [x] Backend completo com todos os endpoints
- [x] Migração de dados históricos
- [x] Página de Transações (tabela, filtros, paginação, importação, edição inline, sugestão de regras com selector de substring)
- [x] Página de Categorias (CRUD de categorias e subcategorias)
- [x] Página de Regras (criação, listagem, remoção e aplicação em massa de regras de categorização)
- [x] Página de Estatísticas (resumo mensal, evolução gráfica, média e mediana por categoria)