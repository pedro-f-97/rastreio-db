# Arquitetura

## Stack

- **Backend**: Python 3.14, FastAPI, SQLAlchemy, SQLite
- **Frontend**: React + Vite, Recharts para gráficos
- **Distribuição**: PyInstaller (Windows + Linux), CI/CD via GitHub Actions

## Estrutura geral

```
backend/    # API FastAPI + modelos SQLAlchemy + lógica de negócio
frontend/   # SPA React
docs/       # Documentação (este ficheiro, modelo de dados, guia de desenvolvimento)
```

## Backend

- **`main.py`**: ponto de entrada, configuração de CORS, montagem dos routers
- **`database.py`**: modelos SQLAlchemy e ligação à BD. A BD é `dados/rastreio.db` dentro de uma pasta-base resolvida por `_resolver_base_dir()`, por esta ordem: a variável de ambiente `RASTREIO_DB_DIR`, se definida (instalações sem permissões de escrita junto ao executável, e os testes); `dirname(sys.executable)` quando empacotado (`sys.frozen`), para manter os dados junto ao executável; e `backend/` em dev
- **`schemas.py`**: schemas Pydantic para validação de entrada/saída da API
- **`routers/`**: um ficheiro por domínio (categorias, contas, transações, património, etc.). Cada novo domínio funcional ganha o seu próprio router, montado em `main.py`
- **Migrações**: cada alteração de schema é uma migração numerada na lista `MIGRACOES` de `database.py`, e a BD guarda em `PRAGMA user_version` a última que levou. As que faltam correm no arranque (`criar_tabelas`) e, num restauro, no ficheiro temporário do backup, antes de este ser validado. Uma BD nova fica logo na última versão. Para mudar o schema, muda-se o modelo e acrescenta-se no fim da lista (nunca se tira nem se troca a ordem) uma função que recebe o caminho da BD, a leva ao mesmo estado, devolve se mudou alguma coisa e é idempotente; para recriar uma tabela, preservam-se os IDs e as FKs. Uma tabela nova não precisa de migração, porque o `create_all` a cria. Se, depois das migrações, ainda faltar alguma coluna do modelo, o arranque recusa com uma mensagem que diz o que falta (`colunas_em_falta`), e o restauro recusa o backup
- **Dados iniciais**: as listas de categorias, subcategorias e tipos de ativo e a função que as cria (`semear_dados_iniciais`) estão em `dados_iniciais.py`; o endpoint `/configuracao/inicializar` chama-a, e ela cria só o que falta, pelo nome

## Frontend

- **`pages/`**: uma página por rota principal, agrupadas na navegação (`GRUPOS_NAV` em `App.jsx`) em Transações, Configuração e Análise
- **`api/`**: um ficheiro por domínio, espelhando os routers do backend; todos usam a instância partilhada `client.js` (nunca `axios` diretamente) para garantir base URL correta em dev vs. `.exe`
- **`components/`**: componentes verdadeiramente reutilizáveis entre páginas (ex. highlight do tour guiado). Sub-componentes específicos de uma página ficam inline no próprio ficheiro da página — não há padrão de extração automática
- **`contexts/`**: estado partilhado entre componentes (ex. `GuiaContext` para o tour guiado)
- **`utils/`**: helpers puros (ex. `formatacao.js` para formatação monetária `pt-PT`)
- **Estilo**: CSS por página (`Pagina.jsx` + `Pagina.css`), com `componentes.css` para classes genéricas partilhadas (`.accoes`, `.lista-itens`).

## CI/CD

- `.github/workflows/build.yml`: build automático (Windows + Linux) disparado por tags de versão, publica executáveis como GitHub Release

## Convenção para novas funcionalidades

Uma feature nova tipicamente atravessa, por esta ordem:
1. Modelo em `database.py` (+ migração em `MIGRACOES`, se mudar uma tabela que já existe)
2. Schema Pydantic em `schemas.py`
3. Router novo ou endpoint num router existente
4. Ficheiro de API no frontend (`api/dominio.js`)
5. Página ou secção de página que consome a API
