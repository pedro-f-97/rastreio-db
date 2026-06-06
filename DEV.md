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
- Frontend disponível em: `http://localhost:5173`

## Arrancar o servidor
```bash
cd backend
source venv/bin/activate
uvicorn main:app --reload --port 9742
```
- API disponível em: `http://localhost:8000`
- Documentação interativa: `http://localhost:8000/docs`
- O `--reload` reinicia automaticamente quando guardas ficheiros

## Recriar a base de dados (apaga tudo!)
```bash
cd backend
rm dados/rastreio.db
python database.py
python popular_bd.py
python migrar_excel.py
```

## Gerar executável
```bash
cd /home/pedrof/Documents/Projectos/rastreio-db
./build.sh
```
- Executável gerado em: `dist_executavel/rastreio-db`
- Base de dados em: `dist_executavel/dados/rastreio.db`
- Para testar com BD nova: `rm dist_executavel/dados/rastreio.db`

## Matar o executável em background
```bash
pkill -f rastreio-db
```

## Git — guardar trabalho
```bash
cd /home/pedrof/Documents/Projectos/rastreio-db
git add backend/ficheiro.py
git commit -m "descrição do que fizeste"
```