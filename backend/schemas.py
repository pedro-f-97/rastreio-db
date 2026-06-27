from pydantic import BaseModel, ConfigDict, model_validator
from typing import Optional
from datetime import date
from database import TipoCategoria, TipoAtivo, TipoMovimento, TipoContabilizacao

# --- SCHEMAS DE CATEGORIA ---
class CategoriaBase(BaseModel):
    nome: str
    tipo: TipoCategoria = TipoCategoria.despesa

class CategoriaCreate(CategoriaBase):
    pass

class Categoria(CategoriaBase):
    id: int
    # Ativa a leitura de modelos ORM (SQLAlchemy) no Pydantic V2
    model_config = ConfigDict(from_attributes=True)

# --- SCHEMAS DE SUBCATEGORIA ---
class SubcategoriaBase(BaseModel):
    nome: str
    categoria_id: int

class SubcategoriaCreate(BaseModel):
    nome: str
    trata_patrimonio: Optional[bool] = None

class Subcategoria(SubcategoriaBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

# --- SCHEMAS DE TRANSAÇÃO ---
class TransacaoBase(BaseModel):
    data: date
    descricao: str
    valor: float
    saldo: Optional[float] = None
    reembolso: bool = False
    notas: Optional[str] = None
    categoria_id: Optional[int] = None
    subcategoria_id: Optional[int] = None

class TransacaoUpdate(BaseModel):
    categoria_id: Optional[int] = None
    subcategoria_id: Optional[int] = None
    reembolso: Optional[bool] = None
    notas: Optional[str] = None

class Transacao(TransacaoBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

# --- SCHEMAS DE REGRAS ---
class RegraBase(BaseModel):
    palavra_chave: str
    categoria_id: int
    subcategoria_id: Optional[int] = None

class RegraCreate(RegraBase):
    pass

class Regra(RegraBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

from database import TipoCategoria, ModoValor, TipoFicheiro

class PerfilImportacaoBase(BaseModel):
    nome: str
    tipo_ficheiro: TipoFicheiro = TipoFicheiro.xlsx
    linha_inicio_dados: int
    coluna_data: int
    formato_data: str
    coluna_descricao: int
    modo_valor: ModoValor
    coluna_valor: Optional[int] = None
    coluna_debito: Optional[int] = None
    coluna_credito: Optional[int] = None
    separador_decimal: str = "."
    tem_saldo: bool = False
    coluna_saldo: Optional[int] = None
    coluna_fee: Optional[int] = None
    conta_id: Optional[int] = None

    @model_validator(mode='after')
    def validar_perfil(self):
        for campo in ['coluna_data', 'coluna_descricao', 'coluna_valor', 'coluna_debito', 'coluna_credito', 'coluna_saldo', 'coluna_fee']:
            v = getattr(self, campo)
            if v is not None and v < 0:
                raise ValueError(f"{campo} não pode ser negativo")
        if self.modo_valor == ModoValor.coluna_unica and self.coluna_valor is None:
            raise ValueError("coluna_valor obrigatória para modo coluna_unica")
        if self.modo_valor == ModoValor.duas_colunas and (self.coluna_debito is None or self.coluna_credito is None):
            raise ValueError("coluna_debito e coluna_credito obrigatórias para modo duas_colunas")
        if self.tem_saldo and self.coluna_saldo is None:
            raise ValueError("coluna_saldo obrigatória quando tem_saldo é True")
        return self

class PerfilImportacaoCreate(PerfilImportacaoBase):
    pass

class PerfilImportacao(PerfilImportacaoBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

# --- SCHEMAS DE ATIVO ---
class AtivoBase(BaseModel):
    nome: str
    tipo: TipoAtivo
    simbolo: Optional[str] = None
    moeda: str = "EUR"
    notas: Optional[str] = None
    contabilizacao: TipoContabilizacao

class AtivoCreate(AtivoBase):
    pass

class Ativo(AtivoBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

# --- SCHEMAS DE MOVIMENTO DE ATIVO ---
class MovimentoAtivoBase(BaseModel):
    ativo_id: int
    transacao_id: Optional[int] = None
    tipo_movimento: TipoMovimento
    data: date
    quantidade: Optional[float] = None
    preco_unitario: Optional[float] = None
    comissao: Optional[float] = 0
    valor_total: float
    notas: Optional[str] = None

class MovimentoAtivoCreate(MovimentoAtivoBase):
    pass

class MovimentoAtivo(MovimentoAtivoBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

# --- SCHEMAS DE PREÇO DE ATIVO ---
class PrecoAtivoBase(BaseModel):
    ativo_id: int
    data: date
    preco: float

class PrecoAtivoCreate(PrecoAtivoBase):
    pass

class PrecoAtivo(PrecoAtivoBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

# --- SCHEMA DE PENDENTE ---
class TransacaoPendente(BaseModel):
    id: int
    data: date
    descricao: str
    valor: float
    subcategoria_id: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)

# --- SCHEMAS DE CONTA ---
class ContaBase(BaseModel):
    nome: str
    saldo_referencia: float = 0.0
    data_referencia: date
    ativa: bool = True

class ContaCreate(ContaBase):
    pass

class ContaUpdate(BaseModel):
    nome: Optional[str] = None
    saldo_referencia: Optional[float] = None
    data_referencia: Optional[date] = None
    ativa: Optional[bool] = None

class Conta(ContaBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class AssociarConta(BaseModel):
    conta_id: Optional[int] = None