# Notas de Desenvolvimento

> **Apontamentos pessoais do utilizador.** Não são instruções para agentes nem
> documentação do projecto: as regras para agentes estão em `AGENTS.md` e o
> guia de desenvolvimento em `docs/desenvolvimento.md`.
>
> Em dev, `backend/dados/rastreio.db` **é a BD real**. Os comandos que a apagam
> ou alteram usam uma pasta à parte via `RASTREIO_DB_DIR`.

## Onde estou?
```bash
pwd
```

## Navegar para o projeto
```bash
cd ~/Documents/Projectos/rastreio-db
```

## Ativar o ambiente virtual
```bash
cd backend
source venv/bin/activate
```
O prompt passa a mostrar `(venv)` quando está ativo.

## Arrancar o frontend
```bash
cd frontend
npm run dev
```
- Frontend disponível em: `http://localhost:9743`
- Proxy para `/api` configurado no Vite, aponta para o backend em `9742`

## Arrancar o servidor
```bash
cd backend
source venv/bin/activate
uvicorn main:app --reload --port 9742
```
- API disponível em: `http://localhost:9742`
- Documentação interativa: `http://localhost:9742/docs`
- O `--reload` reinicia automaticamente quando guardas ficheiros

## Criar uma base de dados nova (sem tocar na real)
```bash
cd backend
source venv/bin/activate
export RASTREIO_DB_DIR=/tmp/rastreio-nova   # a BD fica em /tmp/rastreio-nova/dados/rastreio.db
python database.py
python dados_iniciais.py
uvicorn main:app --reload --port 9742       # no mesmo terminal, para herdar a variável
```
`dados_iniciais.py` semeia apenas a estrutura de categorias/subcategorias — não é ponto de partida para dados de transações.

Para substituir mesmo a BD real, fazer primeiro um backup (botão de backup na página Transações, ou `cp backend/dados/rastreio.db ~/rastreio-backup-$(date +%F).db`) e só depois mexer no ficheiro.

## Comandos SQL
Sobre uma cópia, nunca sobre a BD real (um `DELETE` ou `UPDATE` escrito à mão não tem rollback):
```bash
cp ~/Documents/Projectos/rastreio-db/backend/dados/rastreio.db /tmp/rastreio-copia.db
sqlite3 /tmp/rastreio-copia.db "SELECT * FROM precos_ativo;"
```

## Gerar executável

### Linux
```bash
cd ~/Documents/Projectos/rastreio-db
./build.sh
```

### Windows
```bat
cd C:\caminho\para\rastreio-db
build.bat
```

- Executável gerado em: `dist_executavel/rastreio-db` (Linux) ou `dist_executavel\rastreio-db.exe` (Windows)
- Base de dados em: `dist_executavel/dados/rastreio.db`
- Para testar com BD nova sem perder a actual: `mv dist_executavel/dados/rastreio.db dist_executavel/dados/rastreio.db.guardada` (repor com o `mv` inverso)
- O ícone da janela tkinter (`tray.py`) é carregado a partir de `backend/assets/icon.ico` / `icon.png`, incluídos no executável via `--add-data`
- No Windows, o build usa `--windowed`, o que esconde a consola cmd mas também suprime qualquer `print()` — não usar para debug de arranque no Windows

## Matar o executável em background
```bash
pkill -f rastreio-db
```

## Git
Dar commit de alterações
```bash
cd ~/Documents/Projectos/rastreio-db
git add backend/ficheiro.py
git commit -m "descrição do que fizeste"
```
Marcar para release (gera executáveis)
```bash
git tag -a vX.Y.Z -m "vX.Y.Z: resumo das alterações"
git push origin vX.Y.Z
```