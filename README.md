<p align="center">
  <img src="frontend/src/assets/nariz.svg" width="120" alt="Rastreio-DB" />
</p>

# Rastreio-DB

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

### Transações
- **Transações** — listagem paginada com edição inline de categoria, subcategoria, reembolso e notas; filtros por ano, mês e categoria; filtro rápido de transações por categorizar; categorização automática por regras de substring com sugestões de novas regras; aplicação de regras em massa com resolução individual de conflitos
- **Histórico** — totais agregados por ano e mês, com drill-down por categoria dentro de cada mês
- **Importação** — suporte a Excel e CSV, com perfis de mapeamento de colunas configuráveis por banco e detecção automática de duplicados por `data + descrição + valor + saldo`

### Configuração
- **Categorias** — CRUD completo com definição de tipo (`despesa`, `receita`, `investimento`, `transferencia`) e subcategorias opcionais
- **Regras** — regras de categorização automática por correspondência de substring
- **Contas** — CRUD de contas bancárias

### Análise
- **Estatísticas** — resumo mensal, gráfico de evolução, médias e medianas por categoria, distribuição com drill-down para subcategorias, taxa de poupança e totalizadores anuais
- **Património** — acompanhamento de activos com movimentos, valorização ao longo do tempo e totais por tipo

### Geral
- Tema claro/escuro com persistência entre sessões
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

- Consistência visual e refinamento de estilos nas páginas de Contas e Património
- Exportação de transações para Excel/CSV
- Exportação de relatório de estatísticas
- Modo de revisão de importação — confirmar/rejeitar transações individualmente antes de inserir na BD
- Possibilidade de ligação a BD remota
- Integração opcional com API de preços de mercado (com toggle)
- Vista IRS — ganhos realizados agrupados por categoria de activo

## Arquitectura

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
            │   └── TabelaTransacoes.jsx
            └── pages/
                ├── Categorias.jsx + .css
                ├── Contas.jsx + .css
                ├── Estatisticas.jsx + .css
                ├── Historico.jsx
                ├── Importacao.jsx + .css
                ├── Patrimonio.jsx + .css
                ├── PrimeiroUso.jsx
                ├── Regras.jsx + .css
                └── Transacoes.jsx + .css
```

## Modelo de dados

- **Categoria** — agrupa transações por natureza, com campo `tipo` (`despesa`, `receita`, `investimento`, `transferencia`) que controla como cada categoria é tratada nas estatísticas
- **Subcategoria** — divisão opcional dentro de cada categoria, com flag `trata_patrimonio` para identificar subcategorias relevantes para o módulo de Património
- **Transacao** — registo de cada movimento bancário, com categoria, subcategoria, conta associada, flag de reembolso e notas livres
- **RegraCategorizacao** — regras por substring que permitem categorizar automaticamente transações com base na descrição
- **PerfilImportacao** — configuração de mapeamento de colunas para um banco específico, com suporte a coluna de valor única ou separada em débito/crédito, e associação opcional a uma conta
- **Conta** — conta bancária com saldo e data de referência, associada a transações e perfis de importação; pode ser desactivada sem perda de dados
- **Ativo** — activo patrimonial com tipo (`etf`, `crypto`, `veiculo`, `imovel`, `outro`), símbolo opcional e moeda
- **MovimentoAtivo** — registo de compra, venda ou dividendo sobre um activo, com quantidade, preço unitário, comissão e ligação opcional a uma transação
- **PrecoAtivo** — histórico de valorização de um activo, com unicidade por activo e data