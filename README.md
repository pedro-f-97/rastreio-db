# rastreio-db

Aplicação web para gestão e análise de despesas bancárias pessoais. Permite importar extratos bancários em Excel, categorizar transações automaticamente com regras configuráveis e acompanhar a evolução financeira através de estatísticas detalhadas — com detalhes por categoria, taxa de poupança e totalizadores anuais e absolutos.

## Motivação

O Excel como ferramenta de controlo financeiro acumula limitações que se tornam progressivamente mais frustrantes, este projeto nasceu da necessidade de algo mais robusto e adequado ao problema.

## Preview

### Lista de transações (edição inline + filtros)
![Lista de Transações](docs/screenshots/list.jpg)

### Estatísticas (Mensais, por categoria e subcategorias)
![Estatísticas - Visão Geral](docs/screenshots/stats1.jpg)
![Estatísticas - Detalhe](docs/screenshots/stats2.jpg)

## Funcionalidades

- Importação de extratos Excel exportados do banco, com deteção automática de duplicados por `data + descrição + valor + saldo`
- Categorização automática por regras de substring, com sugestões de novas regras durante o uso
- Edição inline de categoria, subcategoria, reembolso e notas directamente na tabela de transações
- Filtros por ano, mês e categoria; filtro rápido de transações por categorizar
- Aplicação de regras em massa com resolução individual de conflitos
- Estatísticas com resumo mensal, gráfico de evolução, médias e medianas por categoria, distribuição com drill-down para subcategorias, taxa de poupança e totalizadores anuais
- Backup e restauro da base de dados com auto-backup de segurança antes de cada restauro
- Ecrã de primeiro uso com inicialização opcional de categorias predefinidas

## Tecnologias

- **Backend:** Python 3.14 + FastAPI + SQLAlchemy + SQLite
- **Frontend:** React + Vite
- **Servidor:** Uvicorn
- **Distribuição:** PyInstaller

## Categorias

As categorias e subcategorias são totalmente configuráveis. Cada categoria tem um `tipo` que determina o seu papel nas estatísticas:

| Tipo | Papel nas estatísticas |
|---|---|
| `despesa` | Incluída nos totais de despesa e nas médias por categoria |
| `receita` | Incluída nos totais de receita e no cálculo da taxa de poupança |
| `investimento` | Tratada separadamente, não distorce despesa nem receita |
| `transferencia` | Excluída de todas as métricas (movimentos internos entre contas) |

Na primeira utilização, é possível carregar um conjunto de categorias predefinidas como ponto de partida, ou começar do zero.

## Decisões de design

- Reembolsos são tratados como redução de despesa, não como receita (evita inflacionar o total de entradas)
- Transferências internas são excluídas de todas as métricas para não distorcer os dados reais
- O sistema de regras usa correspondência por substring — simples e previsível para o utilizador
- A base de dados fica em `dados/rastreio.db`, junto ao executável, para portabilidade e visibilidade directa do ficheiro

## Distribuição

A aplicação é distribuída como executável portable. O build é específico para o sistema operativo onde é executado.

### Linux

```bash
chmod +x build.sh
./build.sh
```

### Windows

Executar `build.bat` numa máquina Windows.

Em ambos os casos, o executável é gerado em `dist_executavel/`.

> **Nota:** A base de dados fica em `dist_executavel/dados/rastreio.db`. Esta pasta deve ser preservada entre actualizações.

### Primeiro uso

A aplicação abre automaticamente no browser em `http://localhost:8000`. Uma pequena janela de controlo permite reabrir o browser ou encerrar a aplicação.

## Estado

A aplicação está funcional e em uso activo. Cobre o ciclo completo de importação, categorização, análise e backup. Não há funcionalidades parciais ou conhecidamente instáveis.

## Desenvolvimento

### Requisitos

- Python 3.14+
- Node.js 18+

### Backend

```bash
cd backend
pip install -r requirements.txt
python main.py
```

O backend fica disponível em `http://localhost:9742`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

O frontend fica disponível em `http://localhost:9743`, com proxy para o backend configurado no Vite.

## Licença

Este projeto está licenciado sob a [GNU General Public License v3.0](LICENSE).

## Roadmap

- Importação compatível com múltiplos bancos, com perfis de mapeamento de colunas configuráveis pelo utilizador

## Arquitectura

```
rastreio-db/
├── README.md
├── DEV.md
├── build.sh                 # Script de build Linux
├── build.bat                # Script de build Windows
├── backend/
│   ├── database.py          # Modelos SQLAlchemy e ligação à BD
│   ├── main.py              # Ponto de entrada FastAPI + CORS
│   ├── schemas.py           # Schemas Pydantic para validação de dados
│   ├── popular_bd.py        # Categorias e subcategorias predefinidas
│   ├── tray.py              # Janela de controlo para abrir o browser e encerrar a aplicação
│   ├── requirements.txt
│   └── routers/
│       ├── categorias.py    # CRUD de categorias e subcategorias
│       ├── transacoes.py    # Listagem paginada e edição de transações
│       ├── regras.py        # Regras de categorização automática
│       ├── importacao.py    # Importação de extratos Excel do banco
│       ├── backups.py       # Exportação e restauro da base de dados
│       ├── configuracao.py  # Inicialização e estado da aplicação
│       └── estatisticas.py  # Endpoints de estatísticas e resumos
└── frontend/
    ├── index.html
    ├── vite.config.js
    ├── package.json
    └── src/
        ├── api/             # Clientes axios por domínio
        ├── components/      # Componentes reutilizáveis
        └── pages/           # Transacoes, Categorias, Regras, Estatisticas
```

## Modelo de dados

- **Categoria** — agrupa transações por natureza, com campo `tipo` (`despesa`, `receita`, `investimento`, `transferencia`) que controla como cada categoria é tratada nas estatísticas
- **Subcategoria** — divisão opcional dentro de cada categoria, totalmente configurável pelo utilizador
- **Transacao** — registo de cada movimento bancário, com categoria, subcategoria, flag de reembolso e notas livres
- **RegraCategorizacao** — regras por substring que permitem categorizar automaticamente transações futuras com base na descrição
