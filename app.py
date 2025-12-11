from fastapi import FastAPI, UploadFile, File, HTTPException
import tempfile
import shutil
import os
from src import nfe_xml_parser, danfe_ocr_parser, hybrid_extractor

app = FastAPI()

@app.post("/upload")
async def upload_invoice(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Nome de arquivo inválido")
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.filename}") as tmp:
        shutil.copyfileobj(file.file, tmp)
        path = tmp.name

    try:
        ext = path.split('.')[-1].lower()
        
        # SISTEMA HÍBRIDO - Tenta múltiplas abordagens
        invoice = None
        extraction_method = "unknown"
        
        # PRIMEIRO: Tenta parser específico se for XML
        if ext == "xml":
            try:
                invoice = nfe_xml_parser.extract_from_xml(path)
                extraction_method = "xml_parser"
            except Exception as e:
                print(f"XML parser failed: {e}")
        
        # SEGUNDO: Tenta extração híbrida (regex + spaCy + IA)
        if invoice is None or is_incomplete(invoice):
            try:
                hybrid_result = hybrid_extractor.extract_from_file(path, ext)
                if hybrid_result and is_more_complete(hybrid_result, invoice):
                    invoice = hybrid_result
                    extraction_method = "hybrid"
            except Exception as e:
                print(f"Hybrid extraction failed: {e}")
        
        # TERCEIRO: Fallback para OCR especializado
        if invoice is None or is_incomplete(invoice):
            try:
                if ext == "pdf":
                    ocr_result = danfe_ocr_parser.extract_from_pdf(path)
                elif ext in ("png", "jpg", "jpeg"):
                    ocr_result = danfe_ocr_parser.extract_from_image(path)
                else:
                    ocr_result = None
                
                if ocr_result and is_more_complete(ocr_result, invoice):
                    invoice = ocr_result
                    extraction_method = "ocr"
            except Exception as e:
                print(f"OCR extraction failed: {e}")
        
        if invoice is None:
            return {"error": "Não foi possível extrair dados da nota fiscal"}
        
        # Adiciona metadados sobre o método de extração
        result = invoice if isinstance(invoice, dict) else invoice.model_dump()
        result["extraction_method"] = extraction_method
        result["extraction_completeness"] = calculate_completeness(result)
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro no processamento: {str(e)}")
    finally:
        try:
            os.remove(path)
        except:
            pass

def is_incomplete(invoice_data) -> bool:
    """Verifica se a extração está muito incompleta"""
    if not invoice_data:
        return True
    
    data = invoice_data if isinstance(invoice_data, dict) else invoice_data.model_dump()
    
    # Considera incompleto se faltam campos críticos
    critical_fields = ['numero', 'cnpj_emitente', 'valor_total']
    filled_critical = sum(1 for field in critical_fields if data.get(field))
    
    return filled_critical < 2  # Menos de 2 campos críticos preenchidos

def is_more_complete(new_data, old_data) -> bool:
    """Compara qual extração é mais completa"""
    if not old_data:
        return True
    
    new_dict = new_data if isinstance(new_data, dict) else new_data.model_dump()
    old_dict = old_data if isinstance(old_data, dict) else old_data.model_dump()
    
    new_filled = sum(1 for v in new_dict.values() if v not in [None, "", [], {}])
    old_filled = sum(1 for v in old_dict.values() if v not in [None, "", [], {}])
    
    return new_filled > old_filled

def calculate_completeness(invoice_data) -> float:
    """Calcula percentual de completude da extração"""
    if not invoice_data:
        return 0.0
    
    fields = ['numero', 'data_emissao', 'cnpj_emitente', 'nome_emitente', 
              'cnpj_destinatario', 'nome_destinatario', 'valor_total']
    
    filled = sum(1 for field in fields if invoice_data.get(field))
    return round(filled / len(fields) * 100, 1)