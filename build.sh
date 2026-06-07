#!/bin/bash
set -e  # Para imediatamente se algum comando falhar

RAIZ="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$RAIZ/backend"
FRONTEND="$RAIZ/frontend"
DIST="$RAIZ/dist_executavel"

echo " Início do build — rastreio-db"

# 1. Build do frontend
echo ""
echo " A compilar frontend..."
cd "$FRONTEND"
npm run build

# 2. Copiar frontend compilado para dentro do backend
echo ""
echo " A copiar frontend_dist para o backend..."
rm -rf "$BACKEND/frontend_dist"
cp -r "$FRONTEND/dist" "$BACKEND/frontend_dist"

# 3. Instalar PyInstaller no venv se não estiver instalado
cd "$BACKEND"
source venv/bin/activate
pip install pyinstaller --quiet

# 4. Executar PyInstaller
echo ""
echo "  A empacotar com PyInstaller..."
pyinstaller \
  --noconfirm \
  --onedir \
  --windowed \
  --name rastreio-db \
  --add-data "frontend_dist:frontend_dist" \
  --add-data "routers:routers" \
  main.py

# 5. Organizar output final
echo ""
echo " A organizar pasta de distribuição..."
rm -rf "$DIST"
mkdir -p "$DIST"
cp -r "$BACKEND/dist/rastreio-db/"* "$DIST/"
mkdir -p "$DIST/dados"

# 6. Limpeza
rm -rf "$BACKEND/build"
rm -rf "$BACKEND/dist"
rm -rf "$BACKEND/rastreio-db.spec"
rm -rf "$BACKEND/frontend_dist"

echo ""
echo "   Build concluído!"
echo "   Pasta: $DIST"
echo "   Para executar: $DIST/rastreio-db"