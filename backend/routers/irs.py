from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from sqlalchemy.orm import Session

from database import get_db
from servicos.irs_serv import COLUNAS_CSV, anos_disponiveis, csv_da_tabela, relatorio_do_ano

router = APIRouter(prefix="/irs", tags=["irs"])


@router.get("/anos")
def listar_anos(db: Session = Depends(get_db)):
    return anos_disponiveis(db)


@router.get("/{ano}")
def relatorio(ano: int = Path(ge=2000, le=9999), db: Session = Depends(get_db)):
    return relatorio_do_ano(db, ano)


@router.get("/{ano}/csv")
def exportar_csv(
    ano: int = Path(ge=2000, le=9999),
    tabela: str = Query(),
    db: Session = Depends(get_db),
):
    """Uma tabela do relatório (`vendas`, `dividendos` ou `juros`) em CSV, para
    copiar linha a linha para o Portal das Finanças."""
    if tabela not in COLUNAS_CSV:
        raise HTTPException(status_code=404, detail="Tabela desconhecida.")
    return Response(
        content=csv_da_tabela(relatorio_do_ano(db, ano), tabela),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="irs-{ano}-{tabela}.csv"'},
    )
