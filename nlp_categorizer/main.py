import json
import pandas as pd
import glob

# Pasta com arquivos JSON
pasta_json = "data"

# Padrão para buscar arquivos JSON
arquivos_json = glob.glob(f"{pasta_json}/*.json")

# Coletar dados
dados = []

for arquivo in arquivos_json:
    with open(arquivo, "r", encoding="utf-8") as f:
        conteudo = json.load(f)
        for item in conteudo:
            descricao = item["text"]
            categoria = next(iter(item["cats"]))
            dados.append({"descricao": descricao, "categoria": categoria})

# Transformar em DataFrame
df = pd.DataFrame(dados)

df["formato_fasttext"] = "__label__" + df["categoria"] + " " + df["descricao"]

# Salvar no formato exigido
df["formato_fasttext"].to_csv("dados_fasttext.txt", index=False, header=False)

print("Arquivo pronto para FastText salvo com sucesso! ✅")