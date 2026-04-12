from pydantic import BaseModel

class CategoriaCreate(BaseModel):
    nome: str

class SubcategoriaCreate(BaseModel):
    nome: str
    categoria_id: int