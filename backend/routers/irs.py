from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from database import get_db
from servicos.irs_serv import anos_disponiveis, relatorio_do_ano

router = APIRouter(prefix="/irs", tags=["irs"])


@router.get("/anos")
def listar_anos(db: Session = Depends(get_db)):
    return anos_disponiveis(db)


@router.get("/{ano}")
def relatorio(ano: int = Path(ge=2000, le=9999), db: Session = Depends(get_db)):
    return relatorio_do_ano(db, ano)
