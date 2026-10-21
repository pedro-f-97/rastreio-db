"""Protecção do servidor local contra pedidos vindos de outros sites.

O browser deixa qualquer página enviar um formulário com um ficheiro, ou um
POST sem corpo, para `localhost` sem pedir licença antes; o CORS só impede a
página de ler a resposta. Por isso as escritas só são aceites quando o `Origin`
é o da própria aplicação. Pedidos sem `Origin` (curl, testes) não vêm de um
browser e passam.

Contra o DNS rebinding, em que um site alheio passa a apontar para 127.0.0.1 e
o browser o deixa ler as respostas, o `Host` do pedido tem de ser um destes
nomes (`TrustedHostMiddleware`, ligado em `main.py`).
"""

from fastapi.responses import JSONResponse

METODOS_ESCRITA = {"POST", "PUT", "PATCH", "DELETE"}
ANFITRIOES_PERMITIDOS = ["localhost", "127.0.0.1"]


def criar_verificacao_origem(origens_permitidas: set[str]):
    async def verificar_origem(request, call_next):
        origem = request.headers.get("origin")
        if (
            request.method in METODOS_ESCRITA
            and origem is not None
            and origem not in origens_permitidas
        ):
            return JSONResponse(
                status_code=403,
                content={"detail": "Pedido recusado: vem de outro site."},
            )
        return await call_next(request)

    return verificar_origem
