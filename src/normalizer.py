# limpeza, padronização de datas/numeros
def normalize_cnpj(cnpj: str) -> str:
    # Remove caracteres não numéricos
    return ''.join(filter(str.isdigit, cnpj))

def normalize_valor(valor: str) -> float:
    # Converte "1.234,56" para float 1234.56
    return float(valor.replace('.', '').replace(',', '.'))

def normalize_data(data: str) -> str:
    # Padroniza para YYYY-MM-DD
    import datetime
    try:
        return datetime.datetime.strptime(data, "%d/%m/%Y").strftime("%Y-%m-%d")
    except:
        return data
    