# Build para Windows

## Requisitos

- Python 3.11 ou superior — https://www.python.org/downloads/
  - Durante a instalação, marcar "Add Python to PATH"
- Node.js 18 ou superior — https://nodejs.org/

## Passos

1. Clonar o repositório ou descarregar o código fonte
2. Criar o ambiente virtual e instalar dependências:
```cmd
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```
3. Instalar dependências do frontend:
```cmd
cd frontend
npm install
```
4. Correr o script de build:
```cmd
build.bat
```
5. O executável está em `dist_executavel\rastreio-db.exe`

## Notas

- A base de dados fica em `dist_executavel\dados\rastreio.db`
- Esta pasta deve ser preservada entre actualizações