# scripts para treinar/retreinar o modelo spacy
import spacy
from spacy.training import Example

TRAIN_DATA = [
    (
        "Nota Fiscal 12345\nCNPJ: 12.345.678/0001-99\nEmitente: Empresa XYZ\nValor Total: R$ 1.234,56",
        {"entities": [(12, 17, "NUMERO"), (25, 43, "CNPJ"), (55, 65, "EMITENTE"), (79, 89, "VALOR_TOTAL")]}
    ),
    (
        """PREFEITURA DE SÃO JOSÉ DOS CAMPOS
        ...
        Data e Hora de Emissão da NFS-e Competência da NFS-e Número / Série Código de Verificação
        29/09/2025 16:14:34 09/2025 414 / E R6L1oNBg5
        ...
        CPF/CNPJ: Inscrição Municipal:
        31.339.613/0001-81
        344608
        Nome/Razão Social
        31.339.613 AISLAN PEREIRA MACHADO E-mail:
        naoinformado@email.com
        ...
        CPF/CNPJ: Inscrição Municipal:
        16.950.334/0001-66 -
        Nome/Nome E-mail:
        PENIEL MONTAGEM MANUTENÇÃO INDUSTRIAL LTDA - EPP financeiro@grupopeniel.com
        ...
        VALOR TOTAL DA NOTA
        Base Cálculo ISSQN (R$) Retenções (R$) Descontos (R$) Valor Líquido (R$)
        26.000,00 0,00 0,00 26.000,00
        """,
        {
            "entities": [
                # Use o próprio texto para calcular os índices:
                (245, 252, "NUMERO"),  # Exemplo: posição de "414 / E"
                (295, 313, "CNPJ_EMITENTE"),  # posição de "31.339.613/0001-81"
                (340, 373, "NOME_EMITENTE"),  # posição de "31.339.613 AISLAN PEREIRA MACHADO"
                (453, 471, "CNPJ_DESTINATARIO"),  # posição de "16.950.334/0001-66"
                (495, 547, "NOME_DESTINATARIO"),  # posição de "PENIEL MONTAGEM MANUTENÇÃO INDUSTRIAL LTDA - EPP"
                (650, 659, "VALOR_TOTAL"),  # posição de "26.000,00"
                (200, 210, "DATA_EMISSAO"),  # posição de "29/09/2025"
            ]
        }
    ),
    # Adicione mais exemplos reais aqui!
]

nlp = spacy.blank("pt")
ner = nlp.add_pipe("ner")

# Adicione os labels
for _, annotations in TRAIN_DATA:
    for ent in annotations.get("entities"):
        ner.add_label(ent[2])

# Treinamento
optimizer = nlp.begin_training()
for i in range(20):
    losses = {}
    for text, annotations in TRAIN_DATA:
        example = Example.from_dict(nlp.make_doc(text), annotations)
        nlp.update([example], losses=losses)
    print(f"Iteração {i}, perdas: {losses}")

# Salve o modelo treinado
nlp.to_disk("src/nlp/spacy_model")