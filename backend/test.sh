#!/bin/bash
# Correr a suite de testes.
#
# Um único comando, com o código de saída do pytest: se algum teste falhar, este
# script falha com o código 1. É o comando a correr antes de qualquer commit
# (ver docs/desenvolvimento.md).
set -e

BACKEND="$(cd "$(dirname "$0")" && pwd)"
PY="$BACKEND/venv/bin/python"

# Não se recorre ao Python do sistema: o venv é o mesmo que o build usa
# (build.sh, passo 3) e é o único onde os pacotes de teste estão instalados.
if [ ! -x "$PY" ]; then
    echo "Venv não encontrado em backend/venv."
    echo ""
    echo "Cria-o com:"
    echo "    cd backend && python -m venv venv"
    echo "    venv/bin/pip install -r requirements-dev.txt"
    exit 1
fi

# O pytest.ini está em backend/ e é de lá que tem de correr: define
# testpaths = tests e pythonpath = ., sem os quais `from database import ...`
# não resolve.
cd "$BACKEND"
exec "$PY" -m pytest "$@"
