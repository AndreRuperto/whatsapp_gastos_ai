import json
import random
from collections import Counter
from tqdm import tqdm

# Carregar os dados existentes
def load_data(filename):
    with open(filename, "r", encoding="utf-8") as f:
        return json.load(f)

# Salvar os novos dados
def save_data(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# Melhor augmentação de texto
def augment_text(text):
    transformations = [
        lambda x: x.replace("comprei", random.choice(["adquiri", "peguei", "obtive"])),
        lambda x: x.replace("paguei", random.choice(["quitei", "acertei", "realizei o pagamento"])),
        lambda x: x.replace("assinatura", random.choice(["subscrição", "plano"])),
        lambda x: "Ontem, " + x.lower(),
        lambda x: "Na semana passada, " + x.lower(),
        lambda x: "Hoje de manhã, " + x.lower(),
        lambda x: "Fiz uma compra onde " + x.lower(),
        lambda x: x.lower() + ", foi um bom negócio!",
    ]
    new_text = text
    num_transforms = random.randint(1, 3)
    for _ in range(num_transforms):
        transformation = random.choice(transformations)
        new_text = transformation(new_text)
    return new_text

# Balanceamento e augmentação
def balance_and_augment(data, min_samples=1000, augment_factor=3):
    category_counts = Counter()
    balanced_data = []
    
    for item in data:
        category = max(item["cats"], key=item["cats"].get)  # Obtém a categoria principal
        category_counts[category] += 1
        balanced_data.append(item)
    
    max_category = max(category_counts.values())
    
    print("Distribuição antes do balanceamento:")
    print(category_counts)
    
    for item in tqdm(data, desc="Gerando novos exemplos"):
        category = max(item["cats"], key=item["cats"].get)
        while category_counts[category] < min_samples:
            new_example = {
                "text": augment_text(item["text"]),
                "cats": item["cats"]
            }
            balanced_data.append(new_example)
            category_counts[category] += 1
    
    print("Distribuição após balanceamento:")
    print(category_counts)
    return balanced_data

if __name__ == "__main__":
    original_data = load_data("data/train_data.json")
    balanced_data = balance_and_augment(original_data, min_samples=1000, augment_factor=3)
    save_data("train_data_v2.json", balanced_data)
    print("Novo conjunto de treinamento salvo em 'train_data_v2.json'")