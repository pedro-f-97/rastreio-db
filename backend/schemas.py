from pydantic import BaseModel
from typing import Optional

class CategoriaCreate(BaseModel):
    nome: str

class SubcategoriaCreate(BaseModel):
    nome: str
    categoria_id: int

class TransacaoUpdate(BaseModel):
    categoria_id: Optional[int] = None
    subcategoria_id: Optional[int] = None
    reembolso: Optional[bool] = None
    notas: Optional[str] = None