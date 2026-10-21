# Build para Windows

## Requisitos

- Python 3.14 ou superior — https://www.python.org/downloads/
  - Durante a instalação, marcar "Add Python to PATH"
- Node.js 22.12 ou superior (ou 20.19 ou superior, no 20) — https://nodejs.org/

## Passos

1. Clonar o repositório ou descarregar o código fonte
2. Na raiz do projecto, instalar as dependências do frontend:
```cmd
cd frontend
npm install
cd ..
```
3. Correr o script de build, também na raiz (cria o ambiente virtual do backend, se ainda não existir, e instala as dependências):
```cmd
build.bat
```
4. O executável está em `dist_executavel\rastreio-db.exe`

## Notas

- A base de dados fica em `dist_executavel\dados\rastreio.db`
- Esta pasta deve ser preservada entre actualizações