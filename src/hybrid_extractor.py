import re
import spacy
from src.models import Invoice, InvoiceItem
from src import nfe_xml_parser, danfe_ocr_parser
import tempfile
import os

class HybridExtractor:
    def __init__(self):
        # Carrega modelo spaCy se disponível
        try:
            self.nlp = spacy.load("pt_core_news_sm")
        except:
            self.nlp = None
            print("spaCy model not available, using regex-only mode")
        
        # Padrões universais para notas fiscais
        self.patterns = {
            'numero': [
                r'(?:N°?|NUMERO|NOTA)\s*[:\-]?\s*(\d{1,9})',
                r'NOTA\s*FISCAL\s*N°?\s*(\d+)',
                r'NF\s*[:\-]?\s*(\d+)',
                r'(\d{9})\s*Série',  # Para DANFE
            ],
            'data_emissao': [
                r'DATA\s*DE?\s*EMISS[AÃ]O\s*[:\-]?\s*(\d{2}/\d{2}/\d{4})',
                r'EMISS[AÃ]O\s*[:\-]?\s*(\d{2}/\d{2}/\d{4})',
                r'(\d{2}/\d{2}/\d{4})\s*\d{2}:\d{2}:\d{2}',  # Data + hora
            ],
            'cnpj': [
                r'CNPJ\s*[:\-]?\s*(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})',
                r'(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})',
            ],
            'valor_total': [
                r'TOTAL\s*DA\s*NOTA\s*[:\-]?\s*R\$\s*([\d.,]+)',
                r'VALOR\s*TOTAL\s*[:\-]?\s*R\$\s*([\d.,]+)',
                r'TOTAL\s*R\$\s*([\d.,]+)',
            ]
        }
    
    def extract_from_file(self, file_path: str, file_ext: str) -> dict:
        """Abordagem universal para qualquer tipo de nota fiscal"""
        
        # Primeiro: extrai texto do arquivo
        raw_text = self._extract_raw_text(file_path, file_ext)
        if not raw_text or len(raw_text.strip()) < 50:
            return None
        
        # Extrai campos com múltiplas estratégias
        campos = {}
        
        # 1. Extração com regex
        campos.update(self._extract_with_regex(raw_text))
        
        # 2. Extração com spaCy (se disponível)
        if self.nlp:
            campos.update(self._extract_with_spacy(raw_text))
        
        # 3. Validação e correção de campos
        campos = self._validate_and_correct(campos, raw_text)
        
        return Invoice(**campos).model_dump()
    
    def _extract_raw_text(self, file_path: str, file_ext: str) -> str:
        """Extrai texto de qualquer tipo de arquivo"""
        try:
            if file_ext == "xml":
                # Para XML, usa parser estruturado primeiro
                try:
                    xml_data = nfe_xml_parser.extract_from_xml(file_path)
                    # Converte dados XML para texto para regex/spaCy
                    return self._xml_data_to_text(xml_data)
                except:
                    # Fallback: extrai texto bruto do XML
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        return f.read()
            
            elif file_ext == "pdf":
                return danfe_ocr_parser.DANFEParser()._extract_text_from_pdf(file_path)
            
            elif file_ext in ("png", "jpg", "jpeg"):
                return danfe_ocr_parser.DANFEParser()._extract_text_from_image(file_path)
            
            else:
                # Para outros formatos (txt, csv, etc.)
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    return f.read()
                    
        except Exception as e:
            print(f"Error extracting raw text: {e}")
            return ""
    
    def _extract_with_regex(self, text: str) -> dict:
        """Extrai campos usando padrões regex"""
        campos = {}
        
        # Número da nota
        for pattern in self.patterns['numero']:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                campos['numero'] = match.group(1)
                break
        
        # Data de emissão
        for pattern in self.patterns['data_emissao']:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                campos['data_emissao'] = match.group(1)
                break
        
        # CNPJs (identifica emitente vs destinatário)
        cnpjs = []
        for pattern in self.patterns['cnpj']:
            cnpjs.extend(re.findall(pattern, text))
        
        # Heurística: primeiro CNPJ geralmente é emitente
        if cnpjs:
            campos['cnpj_emitente'] = cnpjs[0]
            if len(cnpjs) > 1:
                campos['cnpj_destinatario'] = cnpjs[1]
        
        # Valor total
        for pattern in self.patterns['valor_total']:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                valor = self._normalize_value(match.group(1))
                if valor:
                    campos['valor_total'] = valor
                break
        
        return campos
    
    def _extract_with_spacy(self, text: str) -> dict:
        """Usa spaCy para extração de entidades nomeadas"""
        if not self.nlp or len(text) > 1000000:  # Limite para performance
            return {}
        
        try:
            doc = self.nlp(text[:500000])  # Processa apenas primeira parte para performance
            campos = {}
            
            # Mapeia entidades do spaCy para nossos campos
            for ent in doc.ents:
                if ent.label_ in ["NUMERO_NF", "NUMERO"] and not campos.get('numero'):
                    campos['numero'] = ent.text
                elif ent.label_ in ["DATA", "DATA_EMISSAO"] and not campos.get('data_emissao'):
                    campos['data_emissao'] = ent.text
                elif ent.label_ in ["CNPJ", "CNPJ_EMITENTE"] and not campos.get('cnpj_emitente'):
                    campos['cnpj_emitente'] = ent.text
                elif ent.label_ in ["VALOR", "VALOR_TOTAL"] and not campos.get('valor_total'):
                    campos['valor_total'] = self._normalize_value(ent.text)
            
            return campos
        except Exception as e:
            print(f"spaCy extraction error: {e}")
            return {}
    
    def _validate_and_correct(self, campos: dict, text: str) -> dict:
        """Valida e corrige campos extraídos"""
        result = campos.copy()
        
        # Remove CNPJs inválidos (ex: 00.000.000/0000-00)
        for cnpj_field in ['cnpj_emitente', 'cnpj_destinatario']:
            if result.get(cnpj_field) and '000000000000' in result[cnpj_field]:
                result[cnpj_field] = None
        
        # Tenta encontrar nomes se não encontrados
        if not result.get('nome_emitente'):
            result['nome_emitente'] = self._extract_company_name(text, 'EMITENTE')
        
        if not result.get('nome_destinatario'):
            result['nome_destinatario'] = self._extract_company_name(text, 'DESTINATARIO')
        
        return result
    
    def _extract_company_name(self, text: str, tipo: str) -> str:
        """Tenta extrair nome da empresa usando heurística"""
        patterns = [
            f"{tipo}[:\\s]+([A-Z][A-Za-z\\s]+?)(?=\\s*(?:CNPJ|CPF|$|\\n))",
            f"RAZ[AÃ]O SOCIAL[:\\s]+([A-Z][A-Za-z\\s]+?)(?=\\s*(?:CNPJ|CPF|$|\\n))",
            f"NOME[/\\s]RAZ[AÃ]O[:\\s]+([A-Z][A-Za-z\\s]+?)(?=\\s*(?:CNPJ|CPF|$|\\n))"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                # Filtra nomes muito curtos ou inválidos
                if len(name) > 3 and not re.match(r'^\d', name):
                    return name
        return None
    
    def _normalize_value(self, value: str) -> float:
        """Converte valor string para float"""
        if not value:
            return None
        try:
            cleaned = re.sub(r'[^\d,]', '', value)
            cleaned = cleaned.replace('.', '').replace(',', '.')
            return float(cleaned)
        except:
            return None
    
    def _xml_data_to_text(self, xml_data: dict) -> str:
        """Converte dados XML extraídos para texto para processamento adicional"""
        if not xml_data:
            return ""
        
        text_parts = []
        if xml_data.get('numero'):
            text_parts.append(f"NOTA FISCAL {xml_data['numero']}")
        if xml_data.get('data_emissao'):
            text_parts.append(f"DATA EMISSÃO {xml_data['data_emissao']}")
        if xml_data.get('cnpj_emitente'):
            text_parts.append(f"CNPJ EMITENTE {xml_data['cnpj_emitente']}")
        if xml_data.get('nome_emitente'):
            text_parts.append(f"EMITENTE {xml_data['nome_emitente']}")
        if xml_data.get('valor_total'):
            text_parts.append(f"VALOR TOTAL R$ {xml_data['valor_total']}")
        
        return " ".join(text_parts)

# Instância global
extractor = HybridExtractor()

def extract_from_file(file_path: str, file_ext: str) -> dict:
    return extractor.extract_from_file(file_path, file_ext)