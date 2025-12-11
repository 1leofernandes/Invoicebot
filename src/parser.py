# pdf/xml/txt/csv/image -> raw_text
import os
import pdfplumber
from PIL import Image
import pytesseract
import pandas as pd
from lxml import etree

# Configurações do Tesseract - abordagem mais robusta
TESSERACT_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files\Tesseract-OCR\tessdata"
]

# Tentar configurar o Tesseract
try:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATHS[0]
    # Definir variável de ambiente
    os.environ['TESSDATA_PREFIX'] = TESSERACT_PATHS[1]
except Exception as e:
    print(f"Aviso na configuração do Tesseract: {e}")

def check_tesseract_languages():
    """Verifica idiomas disponíveis no Tesseract"""
    try:
        languages = pytesseract.get_languages()
        # print(f"Idiomas disponíveis: {languages}")
        return 'por' in languages
    except Exception as e:
        print(f"Erro ao verificar idiomas: {e}")
        return False

# def parse_pdf(path: str) -> str:
#     text = ""
#     try:
#         with pdfplumber.open(path) as pdf:
#             for page_num, page in enumerate(pdf.pages):
#                 print(f"Processando página {page_num + 1}...")
#                 txt = page.extract_text()
#                 if txt and len(txt.strip()) > 50:  # Limite mínimo de texto
#                     text += txt + "\n"
#                 else:
#                     # fallback: rasterize page and OCR
#                     print(f"Usando OCR na página {page_num + 1}...")
#                     im = page.to_image(resolution=200).original  # Reduzi a resolução para teste
                    
#                     # Tenta diferentes configurações de idioma
#                     try:
#                         if check_tesseract_languages():
#                             ocr_text = pytesseract.image_to_string(im, lang="por")
#                         else:
#                             ocr_text = pytesseract.image_to_string(im)  # Inglês como fallback
#                         text += ocr_text + "\n"
#                     except Exception as ocr_error:
#                         print(f"Erro no OCR: {ocr_error}")
#                         # Última tentativa sem idioma específico
#                         try:
#                             ocr_text = pytesseract.image_to_string(im)
#                             text += ocr_text + "\n"
#                         except:
#                             text += f"[OCR falhou na página {page_num + 1}]\n"
#     except Exception as e:
#         print(f"Erro ao processar PDF: {e}")
#         raise
#     return text

def parse_pdf(path: str) -> str:
    """Versão otimizada para DANFE/NFCe"""
    text = ""
    try:
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                # Tenta extrair texto normalmente
                txt = page.extract_text()
                if txt:
                    text += txt + "\n"
                else:
                    # Para DANFEs, tenta extrair tabelas
                    tables = page.extract_tables()
                    for table in tables:
                        for row in table:
                            text += ' | '.join(str(cell) for cell in row if cell) + "\n"
    except Exception as e:
        print(f"Erro ao processar DANFE: {e}")
        raise
    return text

def parse_image(path: str) -> str:
    img = Image.open(path)
    try:
        if check_tesseract_languages():
            return pytesseract.image_to_string(img, lang="por")
        else:
            return pytesseract.image_to_string(img)
    except Exception as e:
        print(f"Erro no OCR da imagem: {e}")
        return pytesseract.image_to_string(img)  # Fallback para inglês

def parse_xml(path: str) -> str:
    tree = etree.parse(path)
    return etree.tostring(tree, encoding="unicode")

def parse_csv(path: str) -> str:
    df = pd.read_csv(path, dtype=str, sep=None, engine='python')
    return df.to_string()

# Teste de configuração ao importar o módulo
print("=== Configuração do Parser ===")
print(f"TESSDATA_PREFIX: {os.environ.get('TESSDATA_PREFIX', 'Não definido')}")
print(f"Tesseract path: {getattr(pytesseract.pytesseract, 'tesseract_cmd', 'Não configurado')}")
check_tesseract_languages()