import xml.etree.ElementTree as ET
from src.models import Invoice, InvoiceItem
import re

def extract_from_xml(xml_path: str) -> dict:
    """Extrai dados diretamente do XML da NFe"""
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        # Namespace da NFe
        ns = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}
        
        # Encontrar a tag NFe (pode variar)
        nfe_node = root.find('.//nfe:NFe', ns) or root.find('.//NFe')
        
        if nfe_node is None:
            raise ValueError("Estrutura XML inválida para NFe")
        
        infNFe = nfe_node.find('nfe:infNFe', ns) or nfe_node.find('infNFe')
        
        # Dados básicos
        ide = infNFe.find('nfe:ide', ns) or infNFe.find('ide')
        emit = infNFe.find('nfe:emit', ns) or infNFe.find('emit')
        dest = infNFe.find('nfe:dest', ns) or infNFe.find('dest')
        total = infNFe.find('nfe:total', ns) or infNFe.find('total')
        
        # Extração dos campos
        numero = get_text(ide, 'nNF')
        data_emissao = format_date(get_text(ide, 'dhEmi') or get_text(ide, 'dEmi'))
        
        # Emitente
        cnpj_emitente = get_text(emit, 'CNPJ') or get_text(emit, 'Cnpj')
        nome_emitente = get_text(emit, 'xNome')
        
        # Destinatário
        cnpj_destinatario = get_text(dest, 'CNPJ') or get_text(dest, 'Cnpj')
        nome_destinatario = get_text(dest, 'xNome')
        
        # Itens
        itens = []
        for item in infNFe.findall('.//nfe:det', ns) or infNFe.findall('.//det'):
            prod = item.find('nfe:prod', ns) or item.find('prod')
            if prod is not None:
                descricao = get_text(prod, 'xProd')
                quantidade = float(get_text(prod, 'qCom') or 0)
                valor_unitario = float(get_text(prod, 'vUnCom') or 0)
                valor_total = float(get_text(prod, 'vProd') or 0)
                
                itens.append(InvoiceItem(
                    descricao=descricao,
                    quantidade=quantidade,
                    valor_unitario=valor_unitario,
                    valor_total=valor_total
                ))
        
        # Valor total
        icms_total = total.find('nfe:ICMSTot', ns) or total.find('ICMSTot')
        valor_total = float(get_text(icms_total, 'vNF') or 0)
        
        # Impostos
        impostos = extract_taxes(infNFe, ns)
        
        return Invoice(
            numero=numero,
            data_emissao=data_emissao,
            cnpj_emitente=cnpj_emitente,
            nome_emitente=nome_emitente,
            cnpj_destinatario=cnpj_destinatario,
            nome_destinatario=nome_destinatario,
            itens=itens,
            valor_total=valor_total,
            impostos=impostos
        ).model_dump()
        
    except Exception as e:
        raise Exception(f"Erro na extração XML: {str(e)}")

def get_text(element, tag, namespace=None):
    if element is None:
        return None
    if namespace:
        node = element.find(f'{namespace}:{tag}', namespace)
    else:
        node = element.find(tag)
    return node.text if node is not None else None

def format_date(date_str):
    if not date_str:
        return None
    # Converte 2023-10-15T10:30:00 para 15/10/2023
    match = re.search(r'(\d{4})-(\d{2})-(\d{2})', date_str)
    if match:
        return f"{match.group(3)}/{match.group(2)}/{match.group(1)}"
    return date_str

def extract_taxes(infNFe, ns):
    # Implementar extração de impostos específicos
    return {}