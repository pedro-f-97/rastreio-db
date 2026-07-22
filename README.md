<p align="center">
  <img src="frontend/src/assets/nariz.svg" width="120" alt="Rastreio-DB" />
</p>

<h1 align="center">Rastreio-DB</h1>

<p align="center">
  <a href="https://github.com/pedro-f-97/rastreio-db/releases/latest">⬇️ Download da versão mais recente</a>
</p>

<p align="center">
  <strong>Python • FastAPI • React • SQLite • SQLAlchemy • PyInstaller</strong>
</p>

Aplicação web local e portable para gestão e análise de extratos bancários, sem dependência de serviços externos. Nasceu da necessidade de algo mais robusto do que a típica folha de Excel. Permite importar extratos em Excel (.xlsx, .csv), com perfis configuráveis por banco e conta, categorizar transações automaticamente com regras dinâmicas, marcar transações como património para registo de bens ou investimentos, e acompanhar a evolução financeira através de estatísticas detalhadas.

### Transações
- Listagem paginada com edição inline de categoria, subcategoria, reembolso, conta e notas
- Filtros por ano, mês e categoria, incluindo filtro rápido de transações por categorizar
- Histórico com totais por ano/mês e drill-down por categoria
- Categorização automática por regras de substring, com sugestões automáticas de novas regras
- Aplicação de regras em massa, com resolução individual de conflitos
- Importação de Excel e CSV, com perfis de mapeamento de colunas por banco e conta, com deteção automática de duplicados

### Análise
- Estatísticas mensais: evolução, médias e medianas por categoria, distribuição com drill-down para subcategorias, taxa de poupança e totalizadores anuais
- Ativos: registo de investimentos (ex. ETFs, ações, cripto) e bens (ex. imóveis, viaturas), com histórico de compras, vendas e atualização de preços
- Património: acompanhamento de liquidez, ativos, bens, valorização ao longo do tempo e totais por tipo

### Configuração
- Categorias e subcategorias totalmente configuráveis, com tipo (`despesa`, `receita`, `investimento`, `transferencia`) e toggle para tratamento de património
- Regras de categorização automática
- Gestão de contas bancárias
- Gestão de tipos de ativos

### Geral
- Tema claro/escuro com persistência entre sessões
- Backup e restauro da base de dados, com auto-backup de segurança antes de cada restauro
- Página de primeiro uso com criação opcional de categorias standard, seguido de tour guiado interativo
- Página de Conceitos com explicação das principais áreas e workflow da aplicação

## Preview

### Transações (edição inline + filtros)
![Transações](docs/screenshots/pag_transacoes.png)

### Estatísticas (evolução mensal, distribuição por categoria, taxa de poupança)
![Estatísticas](docs/screenshots/pag_estatisticas.png)

### Património (activos, valorização, FIFO)
![Património](docs/screenshots/pag_patrimonio.png)
![Património — tratar activo](docs/screenshots/pag_patrimonio_tratar.png)

<details>
<summary>Mais screenshots (Importação, Categorias, Regras, Histórico, Contas)</summary>

### Importação (mapeamento de colunas + deteção de duplicados)
![Importação](docs/screenshots/pag_importacao.png)

### Categorias
![Categorias](docs/screenshots/pag_categorias.png)

### Regras de categorização automática
![Regras](docs/screenshots/pag_regras.png)

### Histórico (totais por ano/mês, drill-down por categoria)
![Histórico](docs/screenshots/pag_historico.png)

### Contas
![Contas](docs/screenshots/pag_contas.png)

</details>

## Categorias

As categorias e subcategorias são totalmente configuráveis. Cada categoria tem um `tipo` que determina o seu papel nas estatísticas e cada subcategoria tem um indicador que define se as respectivas transações representam património:

| Tipo | Papel nas estatísticas |
|---|---|
| `despesa` | Incluída nos totais de despesa e nas médias por categoria |
| `receita` | Incluída nos totais de receita e no cálculo da taxa de poupança |
| `investimento` | Tratada separadamente, não distorce despesa nem receita |
| `transferencia` | Excluída de todas as métricas (movimentos internos entre contas) |

Na primeira utilização, é possível carregar um conjunto de categorias predefinidas como ponto de partida, ou começar do zero.

## Património

Transações de subcategorias marcadas com o indicador de património alimentam o módulo de Património. Cada ativo é classificado como:

| Classificação | Papel |
|---|---|
| Investimento | Património com retorno expectável (ex. ETFs, ações, cripto) — conta para o cartão de Investimentos |
| Bem | Património sem retorno expectável (ex. imóvel, viatura) — conta apenas para o total de património |

## Decisões de design

- Reembolsos são tratados como redução de despesa, não como receita, para efeitos de estatísticas
- Transferências internas são excluídas de todas as métricas para não distorcer os dados reais
- O sistema de regras usa correspondência por substring intuitiva
- Regras de categorização sem categoria definida funcionam como "nunca atribuir categoria" a transações correspondentes, para marcar transações a rever manualmente sem forçar uma categoria errada
- A base de dados fica em `dados/rastreio.db`, junto ao executável, para portabilidade e acesso fácil ao ficheiro

## Limitações

- Armazenamento local apenas - sem sincronização entre dispositivos ou cloud - é recomendado utilizar métodos comuns de backup
- Utilizador único, sem gestão de múltiplos perfis

## Documentação adicional

- [Arquitetura do projeto](docs/arquitectura.md)
- [Modelo de dados](docs/modelo-dados.md)
- [Guia de desenvolvimento](docs/desenvolvimento.md)

## Licença

Este projeto está licenciado sob a [GNU General Public License v3.0](LICENSE).
