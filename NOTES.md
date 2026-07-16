# Notas de Desenvolvimento

## Onde estou?
```bash
pwd
```

## Navegar para o projeto
```bash
cd /home/pedrof/Documents/Projectos/rastreio-db
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

## Recriar a base de dados (apaga tudo!)
```bash
cd backend
rm dados/rastreio.db
python database.py
python popular_bd.py
```
`popular_bd.py` semeia apenas a estrutura de categorias/subcategorias — não é ponto de partida para dados de transações.

Se necessário, corre também as migrações relevantes (ver lista abaixo) ou usa `dados_demo.py` para gerar ficheiros xlsx de dados fictícios para importar via UI.

## Comandos SQL
```bash
sqlite3 /home/pedrof/Documents/Projectos/rastreio-db/backend/dados/rastreio.db "SELECT * FROM precos_ativo;"
```

## Gerar executável

### Linux
```bash
cd /home/pedrof/Documents/Projectos/rastreio-db
./build.sh
```

### Windows
```bat
cd C:\caminho\para\rastreio-db
build.bat
```

- Executável gerado em: `dist_executavel/rastreio-db` (Linux) ou `dist_executavel\rastreio-db.exe` (Windows)
- Base de dados em: `dist_executavel/dados/rastreio.db`
- Para testar com BD nova: `rm dist_executavel/dados/rastreio.db`
- O ícone da janela tkinter (`tray.py`) é carregado a partir de `backend/assets/icon.ico` / `icon.png`, incluídos no executável via `--add-data`
- No Windows, o build usa `--windowed`, o que esconde a consola cmd mas também suprime qualquer `print()` — não usar para debug de arranque no Windows

## Matar o executável em background
```bash
pkill -f rastreio-db
```

## Git
Dar commit de alterações
```bash
cd /home/pedrof/Documents/Projectos/rastreio-db
git add backend/ficheiro.py
git commit -m "descrição do que fizeste"
```
Marcar para release (gera executáveis)
```bash
git tag v0.2.2
git push origin v0.2.2
```