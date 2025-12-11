# implementação híbrida (regex + spaCy calls)

import re
import spacy
from src.models import Invoice, InvoiceItem

nlp = spacy.load("src/nlp/spacy_model")
# doc = nlp(raw_text)
# for ent in doc.ents:
#     print(ent.text, ent.label_)


# regex helpers

CNPJ_RE = re.compile(r'(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})')
VAL_RE = re.compile(r'(\d{1,3}(?:\.\d{3})*,\d{2})')
NUM_RE = re.compile(r'(?:Nota\s*Fiscal|NF-e)\s*[:\-]?\s*(\d+)', re.I)
DATE_RE = re.compile(r'(\d{2}/\d{2}/\d{4})')
EMITENTE_RE = re.compile(r'(?:Emitente|Razão Social|Empresa)\s*[:\-]?\s*(.+)')
DESTINATARIO_RE = re.compile(r'(?:Destinatário|Cliente)\s*[:\-]?\s*(.+)')
VAL_TOTAL_RE = re.compile(r'(?:Valor\s*Total|Total\s*da\s*Nota|Valor\s*da\s*Nota)\s*[:\-]?\s*R?\$?\s*([\d.,]+)')

CNPJ_RE = re.compile(r'(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})')
VAL_RE = re.compile(r'(\d{1,3}(?:\.\d{3})*,\d{2})')
# ... outros regex ...

def extract_invoice_data_local(raw_text: str) -> Invoice:
    # 1. Extrai entidades com spaCy
    doc = nlp(raw_text)
    campos_spacy = {}
    for ent in doc.ents:
        campos_spacy[ent.label_] = ent.text

    # 2. Extrai campos com regex (fallback ou complemento)
    numero = campos_spacy.get("NUMERO") or (NUM_RE.search(raw_text).group(1) if NUM_RE.search(raw_text) else None)
    data_emissao = campos_spacy.get("DATA_EMISSAO") or (DATE_RE.search(raw_text).group(1) if DATE_RE.search(raw_text) else None)
    cnpjs = CNPJ_RE.findall(raw_text)
    cnpj_emitente = campos_spacy.get("CNPJ_EMITENTE") or (cnpjs[0] if len(cnpjs) > 0 else None)
    cnpj_destinatario = campos_spacy.get("CNPJ_DESTINATARIO") or (cnpjs[1] if len(cnpjs) > 1 else None)
    nome_emitente = campos_spacy.get("NOME_EMITENTE") or None
    nome_destinatario = campos_spacy.get("NOME_DESTINATARIO") or None
    valor_total = campos_spacy.get("VALOR_TOTAL") or None

    # 3. Itens (regex/heurística)
    itens = []
    linhas = raw_text.split('\n')
    for linha in linhas:
        valores = VAL_RE.findall(linha)
        if len(valores) >= 2:
            partes = re.split(r'\s{2,}|\t|\|', linha)
            descricao = partes[0].strip() if len(partes) > 0 else ""
            quantidade = None
            valor_unitario = None
            valor_total_item = None
            for parte in partes:
                if re.match(r'^\d+$', parte.strip()):
                    quantidade = int(parte.strip())
                elif VAL_RE.match(parte.strip()):
                    if not valor_unitario:
                        valor_unitario = parte.strip()
                    else:
                        valor_total_item = parte.strip()
            if descricao and quantidade and valor_unitario and valor_total_item:
                itens.append(InvoiceItem(
                    descricao=descricao,
                    quantidade=quantidade,
                    valor_unitario=valor_unitario,
                    valor_total=valor_total_item
                ))

    inv = Invoice(
        numero=numero,
        data_emissao=data_emissao,
        cnpj_emitente=cnpj_emitente,
        nome_emitente=nome_emitente,
        cnpj_destinatario=cnpj_destinatario,
        nome_destinatario=nome_destinatario,
        itens=itens,
        valor_total=valor_total,
        impostos={}
    )
    return inv