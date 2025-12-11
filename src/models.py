from pydantic import BaseModel, field_validator
from typing import List, Optional
import re

class InvoiceItem(BaseModel):
    descricao: str
    quantidade: Optional[float] = None
    valor_unitario: Optional[float] = None
    valor_total: Optional[float] = None

class Invoice(BaseModel):
    numero: Optional[str] = None
    data_emissao: Optional[str] = None
    cnpj_emitente: Optional[str] = None
    nome_emitente: Optional[str] = None
    cnpj_destinatario: Optional[str] = None
    nome_destinatario: Optional[str] = None
    itens: List[InvoiceItem] = []
    valor_total: Optional[float] = None
    impostos: dict = {}

    @field_validator('cnpj_emitente', 'cnpj_destinatario')
    @classmethod
    def validate_cnpj(cls, v):
        if v is None:
            return v
        # Remove formatação e valida
        clean_cnpj = re.sub(r'\D', '', v)
        if len(clean_cnpj) == 14:
            return clean_cnpj
        return v

    @field_validator('data_emissao')
    @classmethod
    def validate_date(cls, v):
        if v and re.match(r'\d{2}/\d{2}/\d{4}', v):
            return v
        return None