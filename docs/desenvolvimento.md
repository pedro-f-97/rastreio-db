# Desenvolvimento

## Requisitos
- Python 3.14+
- Node.js 18+

## Clone
```bash
git clone https://github.com/pedro-f-97/rastreio-db.git
cd rastreio-db
```

## Backend

### Criar o ambiente virtual
```bash
cd backend
python -m venv venv
source venv/bin/activate
```

### Instalar e arrancar
```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 9742
```

Fica disponível em `http://localhost:9742`.

## Frontend
```bash
cd frontend
npm install
npm run dev
```

Fica disponível em `http://localhost:9743`, com proxy para o backend configurado no Vite.

## Testes
A suite vive em `backend/tests/` e corre com o `pytest`. O `pytest.ini` está em `backend/`, por isso os testes correm sempre a partir de `backend/` — é lá que estão o `testpaths = tests` e o `pythonpath = .` de que os imports (`from database import ...`) dependem.

### Instalar as dependências de testes
```bash
cd backend
venv/bin/pip install -r requirements-dev.txt
```
O `requirements-dev.txt` inclui o `requirements.txt`, por isso não é preciso instalar os dois.

### Correr os testes
```bash
./backend/test.sh
```
Ou, sem o script:
```bash
cd backend
venv/bin/python -m pytest
```

### Antes de commit
Corre os testes sempre que mexeres em `backend/`. O `test.sh` propaga o código de saída do `pytest`, por isso serve directamente num gancho de pré-commit.

> **Nota:** o `pytest.ini` já traz `-q` nos `addopts`. Não repitas `-q` na linha de comandos: dois `-q` somam-se em `-qq` e escondem a linha final com o resumo.

## Estrutura do projeto
Ver [arquitetura.md](./arquitetura.md).

## Build
A aplicação é distribuída como executável portable, gerado com PyInstaller. O build é específico para o sistema operativo onde é executado — não há cross-compilation.

### Linux
```bash
chmod +x build.sh
./build.sh
```

### Windows
Executar `build.bat` numa máquina Windows.

Em ambos os casos, o executável é gerado em `dist_executavel/`.

> **Nota:** A base de dados fica em `dist_executavel/dados/rastreio.db`. Esta pasta deve ser preservada entre atualizações — apagá-la equivale a perder todos os dados.

### Primeiro arranque do executável
A aplicação abre automaticamente no browser em `http://localhost:9743`. Uma pequena janela de controlo (`tray.py`, tkinter) permite reabrir o browser ou encerrar a aplicação.