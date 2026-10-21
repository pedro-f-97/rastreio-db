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
- **Migrações**: alterações de schema não-triviais (ex. coluna não-nula, recriação de tabela) são feitas via scripts manuais `migrar_*.py` na raiz do backend, usando recriação de tabela para preservar IDs e FKs. Um script obtém a BD do `database` (`DB_PATH`, `engine` ou `SessionLocal`), nunca de um caminho próprio, para que `RASTREIO_DB_DIR` se aplique, e corre primeiro numa cópia. Depois de aplicado, apaga-se: fica no histórico do git
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
1. Modelo em `database.py` (+ migração manual, se aplicável)
2. Schema Pydantic em `schemas.py`
3. Router novo ou endpoint num router existente
4. Ficheiro de API no frontend (`api/dominio.js`)
5. Página ou secção de página que consome a API
