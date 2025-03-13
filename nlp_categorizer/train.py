import spacy
import json
import random
from spacy.training import Example
from tqdm import tqdm
from spacy.util import minibatch

def load_data(filename):
    """Carrega os dados do JSON e retorna no formato necessário para treinamento"""
    with open(filename, "r", encoding="utf-8") as f:
        data = json.load(f)

    train_data = []
    for item in data:
        if "text" in item and "cats" in item:
            train_data.append((item["text"], {"cats": item["cats"]}))
    return train_data

def train_model(train_data, iterations=20, batch_size=16, early_stopping=3):
    """Treina o modelo de NLP do spaCy com os dados fornecidos"""
    nlp = spacy.load("pt_core_news_lg")  # Modelo maior melhora embeddings

    # Adiciona o pipeline de categorização de texto
    if "textcat" in nlp.pipe_names:
        nlp.remove_pipe("textcat")

    textcat = nlp.add_pipe("textcat", last=True)

    # Adiciona categorias dinamicamente
    labels = {cat for _, annotations in train_data for cat in annotations["cats"]}
    for label in labels:
        textcat.add_label(label)

    optimizer = nlp.begin_training()

    print("\n🚀 Iniciando treinamento...\n")

    best_loss = float("inf")
    patience = 0

    for i in range(iterations):
        random.shuffle(train_data)
        losses = {}

        batches = minibatch(train_data, size=batch_size)

        with tqdm(total=len(train_data) // batch_size, desc=f"Iteração {i+1}/{iterations}") as pbar:
            for batch in batches:
                examples = [Example.from_dict(nlp.make_doc(text), annotation) for text, annotation in batch]
                nlp.update(examples, sgd=optimizer, losses=losses)
                pbar.update(1)

        print(f"📉 Iteração {i+1} - Losses: {losses}")

        # Parada antecipada se o loss não melhorar
        if losses["textcat"] >= best_loss:
            patience += 1
            if patience >= early_stopping:
                print(f"\n⏹️ Early stopping ativado após {patience} iterações sem melhoria!\n")
                break
        else:
            best_loss = losses["textcat"]
            patience = 0

    return nlp

if __name__ == "__main__":
    data = load_data("data/train_data_v2.json")
    
    if not data:
        print("❌ Erro: Nenhum dado foi carregado!")
    else:
        nlp_model = train_model(data, iterations=50, batch_size=16, early_stopping=5)  # Configuração ajustada
        nlp_model.to_disk("model_spacy")
        print("\n✅ Modelo treinado e salvo em 'model_spacy' 🎉")