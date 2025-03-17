import json

# Carregar seu JSON original
with open("data/train_data.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# Converter para o formato aceito pelo Open Intent Classifier
converted_data = []

for item in data:
    text = item["text"]
    category = max(item["cats"], key=item["cats"].get)  # Pega a categoria com maior score (geralmente 1.0)
    
    converted_data.append({"text": text, "intent": category})

# Salvar o novo JSON
with open("data/train_data_oic.json", "w", encoding="utf-8") as f:
    json.dump(converted_data, f, indent=4, ensure_ascii=False)

print("✅ Dados convertidos para o formato Open Intent Classifier!")
