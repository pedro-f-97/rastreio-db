# Desenvolvimento

## Requisitos

- Python 3.14+
- Node.js 18+

## Backend

```bash
cd backend
pip install -r requirements.txt
python main.py
```

Fica disponível em `http://localhost:9742`.

## Frontend

```bash
cd frontend
npm install
npm run dev
```

Fica disponível em `http://localhost:9743`, com proxy para o backend configurado no Vite.

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

> **Nota:** A base de dados fica em `dist_executavel/dados/rastreio.db`. Esta pasta deve ser preservada entre actualizações — apagá-la equivale a perder todos os dados.

### Primeiro arranque do executável

A aplicação abre automaticamente no browser em `http://localhost:8000`. Uma pequena janela de controlo (`tray.py`, tkinter) permite reabrir o browser ou encerrar a aplicação.