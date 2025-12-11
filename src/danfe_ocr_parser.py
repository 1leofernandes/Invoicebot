import pdfplumber
import pytesseract
from PIL import Image
import re
import cv2
import numpy as np
import os
import subprocess
from src.models import Invoice, InvoiceItem

class DANFEParser:
    def __init__(self):
        self.tesseract_available = self._setup_tesseract()
    
    def _setup_tesseract(self) -> bool:
        """Configura o Tesseract"""
        try:
            tesseract_paths = [
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            ]
            
            for path in tesseract_paths:
                if os.path.exists(path):
                    pytesseract.pytesseract.tesseract_cmd = path
                    break
            
            tessdata_paths = [
                r"C:\Program Files\Tesseract-OCR\tessdata",
                r"C:\Program Files (x86)\Tesseract-OCR\tessdata",
            ]
            
            for path in tessdata_paths:
                if os.path.exists(path):
                    os.environ['TESSDATA_PREFIX'] = path
                    break
            
            return self._check_available_languages()
            
        except Exception as e:
            print(f"Configuração Tesseract: {e}")
            return False
    
    def _check_available_languages(self) -> bool:
        try:
            cmd = [pytesseract.pytesseract.tesseract_cmd, '--list-langs']
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            if result.returncode == 0:
                languages = result.stdout.strip().split('\n')[1:]
                if 'por' in languages:
                    self.tesseract_lang = 'por'
                    return True
                elif 'eng' in languages:
                    self.tesseract_lang = 'eng'
                    return True
            return False
        except:
            return False

    def extract_from_pdf(self, pdf_path: str) -> dict:
        """Extrai dados de PDF com foco em DANFE"""
        try:
            # PRIMEIRO: Tenta extração de texto nativo (mais confiável para DANFEs)
            text_native = self._extract_native_pdf_text(pdf_path)
            if text_native and len(text_native.strip()) > 100:
                print("=== USANDO TEXTO NATIVO DO PDF ===")
                result = self._parse_danfe_text(text_native, "native")
                if self._is_valid_extraction(result):
                    return result
            
            # SEGUNDO: Tenta OCR apenas se necessário
            if self.tesseract_available:
                text_ocr = self._extract_ocr_text(pdf_path)
                if text_ocr and len(text_ocr.strip()) > 100:
                    print("=== USANDO OCR ===")
                    result = self._parse_danfe_text(text_ocr, "ocr")
                    if self._is_valid_extraction(result):
                        return result
            
            return {"error": "Não foi possível extrair dados suficientes"}
            
        except Exception as e:
            raise Exception(f"Erro na extração PDF: {str(e)}")

    def _extract_native_pdf_text(self, pdf_path: str) -> str:
        """Extrai texto nativo do PDF (mais confiável para DANFEs)"""
        text = ""
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    # Extrai texto
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                    
                    # Extrai tabelas
                    tables = page.extract_tables()
                    for table in tables:
                        for row in table:
                            if any(cell for cell in row if cell):
                                text += ' | '.join(str(cell) for cell in row if cell) + "\n"
        except Exception as e:
            print(f"Erro na extração nativa: {e}")
        return text

    def _extract_ocr_text(self, pdf_path: str) -> str:
        """Extrai texto via OCR"""
        text = ""
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    img = page.to_image(resolution=300).original
                    ocr_text = self._try_ocr_with_fallback(img)
                    if ocr_text:
                        text += ocr_text + "\n"
        except Exception as e:
            print(f"Erro no OCR: {e}")
        return text

    def _try_ocr_with_fallback(self, image) -> str:
        """Tenta OCR com fallbacks de idioma"""
        try:
            if self.tesseract_lang == 'por':
                return pytesseract.image_to_string(image, lang='por')
            else:
                return pytesseract.image_to_string(image, lang='eng')
        except:
            return pytesseract.image_to_string(image)

    def _is_valid_extraction(self, result: dict) -> bool:
        """Verifica se a extração é válida"""
        if 'error' in result:
            return False
        
        # Considera válido se tem pelo menos 2 campos críticos
        critical_fields = ['numero', 'cnpj_emitente', 'valor_total']
        filled = sum(1 for field in critical_fields if result.get(field))
        return filled >= 1

    def _parse_danfe_text(self, text: str, source: str) -> dict:
        """Analisa texto de DANFE com padrões específicos"""
        print(f"=== ANALISANDO DANFE ({source}) ===")
        print(f"Texto completo: {text}")
        
        campos = {}
        
        # 1. NÚMERO DA NOTA
        campos['numero'] = self._extract_numero_danfe(text)
        
        # 2. DATA EMISSÃO
        campos['data_emissao'] = self._extract_data_emissao_danfe(text)
        
        # 3. CNPJs
        cnpj_data = self._extract_cnpjs_danfe(text)
        campos.update(cnpj_data)
        
        # 4. VALOR TOTAL - BUSCA MAIS AGRESSIVA
        campos['valor_total'] = self._extract_valor_total_danfe(text)
        
        # 5. NOMES
        campos['nome_emitente'] = self._extract_nome_emitente_danfe(text)
        campos['nome_destinatario'] = self._extract_nome_destinatario_danfe(text)
        
        # 6. ITENS
        campos['itens'] = self._extract_itens_danfe(text)
        
        print("=== RESULTADO ===")
        for k, v in campos.items():
            if v: print(f"✅ {k}: {v}")
            else: print(f"❌ {k}: None")
        
        return Invoice(**campos).model_dump()

    def _extract_numero_danfe(self, text: str) -> str:
        """Extrai número da nota específico para DANFE"""
        # Padrão: NF-e N. 983.041
        match = re.search(r'NF-e\s*N\.?\s*(\d{3}\.\d{3})', text, re.IGNORECASE)
        if match:
            return match.group(1).replace('.', '')  # Remove pontos
        
        # Padrão: N. 983.041 SÉRIE
        match = re.search(r'N\.?\s*(\d{3}\.\d{3})\s*SÉRIE', text, re.IGNORECASE)
        if match:
            return match.group(1).replace('.', '')
        
        # Procura por 6 dígitos consecutivos
        match = re.search(r'\b(\d{6})\b', text)
        if match:
            return match.group(1)
        
        return None

    def _extract_data_emissao_danfe(self, text: str) -> str:
        """Extrai data de emissão para DANFE"""
        # Procura qualquer data no formato DD/MM/AAAA
        dates = re.findall(r'\b(\d{2}/\d{2}/\d{4})\b', text)
        for date in dates:
            # Valida se é uma data plausível (não muito antiga/futura)
            day, month, year = map(int, date.split('/'))
            if 2020 <= year <= 2030 and 1 <= month <= 12 and 1 <= day <= 31:
                return date
        return None

    def _extract_cnpjs_danfe(self, text: str) -> dict:
        """Extrai CNPJs para DANFE"""
        result = {}
        cnpjs = re.findall(r'\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}', text)
        
        print(f"CNPJs encontrados (formatados): {cnpjs}")
        
        if not cnpjs:
            # Tenta encontrar CNPJs sem formatação
            cnpjs_raw = re.findall(r'\d{14}', text)
            print(f"CNPJs encontrados (raw): {cnpjs_raw}")
            for cnpj_raw in cnpjs_raw:
                # Formata: 12.345.678/0001-99
                formatted = f"{cnpj_raw[:2]}.{cnpj_raw[2:5]}.{cnpj_raw[5:8]}/{cnpj_raw[8:12]}-{cnpj_raw[12:14]}"
                cnpjs.append(formatted)
        
        # Remove duplicatas mantendo a ordem
        cnpjs = list(dict.fromkeys(cnpjs))
        print(f"CNPJs únicos: {cnpjs}")
        
        if len(cnpjs) >= 1:
            result['cnpj_emitente'] = cnpjs[0]
        if len(cnpjs) >= 2:
            result['cnpj_destinatario'] = cnpjs[1]
        
        return result

    def _extract_valor_total_danfe(self, text: str) -> float:
        """Extrai valor total para DANFE - BUSCA MUITO MAIS AGRESSIVA"""
        print("=== BUSCANDO VALOR TOTAL ===")
        
        # ESTRATÉGIA 1: Padrões específicos para "VALOR TOTAL DA NOTA"
        patterns_specific = [
            r'VALOR\s*TOTAL\s*DA\s*NOTA\s*[:\-]?\s*R\s*[$\s]*\s*([\d.,]+)',
            r'TOTAL\s*DA\s*NOTA\s*[:\-]?\s*R\s*[$\s]*\s*([\d.,]+)',
            r'VALOR\s*TOTAL\s*[:\-]?\s*R\s*[$\s]*\s*([\d.,]+)',
            r'TOTAL\s*R\s*[$\s]*\s*([\d.,]+)',
            r'VALOR\s*TOTAL\s*DA\s*NOTA\s*[:\-]?\s*([\d.,]+)',
            r'TOTAL\s*DA\s*NOTA\s*[:\-]?\s*([\d.,]+)',
        ]
        
        for pattern in patterns_specific:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                valor = self._normalize_value(match)
                if valor and valor > 0:
                    print(f"🎯 VALOR TOTAL ENCONTRADO com padrão '{pattern}': {valor}")
                    return valor
        
        # ESTRATÉGIA 2: Busca por linhas que contenham "TOTAL" e capture números próximos
        lines = text.split('\n')
        for i, line in enumerate(lines):
            line_clean = re.sub(r'\s+', ' ', line.strip())
            if any(keyword in line_clean.upper() for keyword in ['TOTAL', 'VALOR TOTAL', 'TOTAL DA NOTA']):
                print(f"📄 Linha com TOTAL: '{line_clean}'")
                
                # Procura valores monetários nesta linha
                valores_linha = re.findall(r'[\d.,]+\s*(?:R\s*[$\s]*|$)', line_clean)
                if not valores_linha:
                    valores_linha = re.findall(r'R\s*[$\s]*\s*([\d.,]+)', line_clean)
                if not valores_linha:
                    valores_linha = re.findall(r'([\d]{1,3}(?:\.\d{3})*,\d{2})', line_clean)
                
                print(f"💰 Valores encontrados na linha: {valores_linha}")
                
                for val in valores_linha:
                    valor_norm = self._normalize_value(val)
                    if valor_norm and valor_norm > 10:  # Filtra valores muito pequenos
                        print(f"🎯 VALOR TOTAL ENCONTRADO na linha: {valor_norm}")
                        return valor_norm
                
                # Se não encontrou na mesma linha, verifica as próximas 3 linhas
                for j in range(i+1, min(i+4, len(lines))):
                    next_line = lines[j].strip()
                    valores_next = re.findall(r'[\d.,]+\s*(?:R\s*[$\s]*|$)', next_line)
                    if not valores_next:
                        valores_next = re.findall(r'R\s*[$\s]*\s*([\d.,]+)', next_line)
                    if not valores_next:
                        valores_next = re.findall(r'([\d]{1,3}(?:\.\d{3})*,\d{2})', next_line)
                    
                    print(f"💰 Valores na linha {j}: {valores_next}")
                    
                    for val in valores_next:
                        valor_norm = self._normalize_value(val)
                        if valor_norm and valor_norm > 10:
                            print(f"🎯 VALOR TOTAL ENCONTRADO na linha seguinte: {valor_norm}")
                            return valor_norm
        
        # ESTRATÉGIA 3: Busca TODOS os valores monetários no texto e pega o MAIOR
        print("🔍 Buscando TODOS os valores monetários no texto...")
        
        # Padrões para valores monetários
        all_monetary_values = []
        
        # Padrão 1: R$ 1.234,56
        all_monetary_values.extend(re.findall(r'R\s*[$\s]*\s*([\d.,]+)', text, re.IGNORECASE))
        
        # Padrão 2: 1.234,56 R$
        all_monetary_values.extend(re.findall(r'([\d.,]+)\s*R\s*[$\s]*', text, re.IGNORECASE))
        
        # Padrão 3: Apenas números no formato monetário (1.234,56)
        all_monetary_values.extend(re.findall(r'\b(\d{1,3}(?:\.\d{3})*,\d{2})\b', text))
        
        # Padrão 4: Números com vírgula decimal
        all_monetary_values.extend(re.findall(r'\b(\d+[.,]\d{2})\b', text))
        
        # Remove duplicatas
        all_monetary_values = list(set(all_monetary_values))
        print(f"💰 TODOS os valores monetários encontrados: {all_monetary_values}")
        
        if all_monetary_values:
            # Converte e filtra valores
            valores_convertidos = []
            for valor_str in all_monetary_values:
                valor_float = self._normalize_value(valor_str)
                if valor_float and valor_float > 10:  # Filtra valores muito pequenos
                    valores_convertidos.append(valor_float)
            
            if valores_convertidos:
                maior_valor = max(valores_convertidos)
                print(f"🎯 MAIOR VALOR ENCONTRADO (fallback): {maior_valor}")
                return maior_valor
        
        print("❌ VALOR TOTAL NÃO ENCONTRADO")
        return None

    def _extract_nome_emitente_danfe(self, text: str) -> str:
        """Extrai nome do emitente para DANFE"""
        lines = text.split('\n')
        
        for i, line in enumerate(lines):
            line_upper = line.upper()
            if any(keyword in line_upper for keyword in ['EMITENTE', 'REMETENTE', 'RAZÃO SOCIAL', 'RAZAO SOCIAL']):
                for j in range(i+1, min(i+4, len(lines))):
                    candidate = lines[j].strip()
                    if (len(candidate) >= 3 and 
                        not re.match(r'^[\d\s\.\-/]+$', candidate) and
                        not any(exclude in candidate.upper() for exclude in ['CNPJ', 'CPF', 'ENDEREÇO', 'RUA', 'AV.', 'AVENIDA', 'BR-', 'KM', 'TELEFONE', 'EMAIL'])):
                        return candidate
        
        return None

    def _extract_nome_destinatario_danfe(self, text: str) -> str:
        """Extrai nome do destinatário para DANFE"""
        lines = text.split('\n')
        
        for i, line in enumerate(lines):
            line_upper = line.upper()
            if any(keyword in line_upper for keyword in ['DESTINATARIO', 'DESTINATÁRIO', 'CLIENTE', 'TOMADOR']):
                for j in range(i+1, min(i+4, len(lines))):
                    candidate = lines[j].strip()
                    if (len(candidate) >= 3 and 
                        not re.match(r'^[\d\s\.\-/]+$', candidate) and
                        not any(exclude in candidate.upper() for exclude in ['CNPJ', 'CPF', 'ENDEREÇO', 'RUA', 'AV.', 'AVENIDA', 'BR-', 'KM', 'TELEFONE', 'EMAIL'])):
                        return candidate
        
        return None

    def _extract_itens_danfe(self, text: str) -> list:
        """Extrai itens simplificado para DANFE"""
        itens = []
        lines = text.split('\n')
        
        for line in lines:
            if re.match(r'^\d', line.strip()):
                parts = line.split()
                if len(parts) >= 2:
                    descricao = ""
                    for part in parts[1:]:
                        if not re.match(r'^\d+[,.]?\d*$', part):
                            descricao += part + " "
                    
                    if descricao.strip():
                        descricao_limpa = re.sub(r'[^\w\s\.\-/]', '', descricao.strip())
                        itens.append(InvoiceItem(
                            descricao=descricao_limpa,
                            quantidade=1,
                            valor_unitario=0,
                            valor_total=0
                        ))
        
        return itens[:5]

    def _normalize_value(self, value: str) -> float:
        """Converte valor para float"""
        if not value:
            return None
        try:
            # Remove R$, espaços
            cleaned = re.sub(r'[R\$\s]', '', value)
            
            # Se tem tanto ponto quanto vírgula
            if ',' in cleaned and '.' in cleaned:
                # Verifica qual é o separador decimal (geralmente o último)
                if cleaned.rfind(',') > cleaned.rfind('.'):
                    # Vírgula é decimal, pontos são milhares: 1.234,56 -> 1234.56
                    cleaned = cleaned.replace('.', '').replace(',', '.')
                else:
                    # Ponto é decimal, vírgulas são milhares: 1,234.56 -> 1234.56
                    cleaned = cleaned.replace(',', '')
            elif ',' in cleaned:
                # Só tem vírgula - assume que é decimal
                cleaned = cleaned.replace(',', '.')
            else:
                # Só tem ponto ou nenhum - já está pronto
                pass
            
            return float(cleaned)
        except Exception as e:
            print(f"Erro ao normalizar valor '{value}': {e}")
            return None

    def extract_from_image(self, image_path: str) -> dict:
        """Extrai de imagem (similar ao PDF)"""
        try:
            if self.tesseract_available:
                img = Image.open(image_path)
                text = self._try_ocr_with_fallback(img)
                if text:
                    return self._parse_danfe_text(text, "image_ocr")
            return {"error": "Não foi possível extrair dados da imagem"}
        except Exception as e:
            raise Exception(f"Erro na extração de imagem: {str(e)}")

# Instância global
parser = DANFEParser()

def extract_from_pdf(pdf_path: str) -> dict:
    return parser.extract_from_pdf(pdf_path)

def extract_from_image(image_path: str) -> dict:
    return parser.extract_from_image(image_path)