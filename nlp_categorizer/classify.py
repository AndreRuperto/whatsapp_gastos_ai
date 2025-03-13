import spacy
import json

# Carrega o modelo treinado
nlp = spacy.load("model_spacy")

def classify_text(text):
    doc = nlp(text)
    cats = doc.cats
    predicted_label = max(cats, key=cats.get)
    confidence = cats[predicted_label]
    return predicted_label, confidence

def evaluate_from_file(test_filename, verification_filename):
    with open(test_filename, "r", encoding="utf-8") as f:
        test_data = json.load(f)
    
    with open(verification_filename, "r", encoding="utf-8") as f:
        verification_data = json.load(f)

    correct_predictions = 0
    total = len(test_data)

    for test_item, verification_item in zip(test_data, verification_data):
        predicted_label, confidence = classify_text(test_item["text"])
        true_label = verification_item["categoria"]

        is_correct = predicted_label == true_label
        if is_correct:
            correct_predictions += 1

        print(f"Texto: {test_item['text']}")
        print(f"Categoria Prevista: {predicted_label} (confiança={confidence:.2f})")
        print(f"Categoria Correta: {true_label}")
        print(f"{'✅ Correto' if is_correct else '❌ Incorreto'}\n")

    accuracy = correct_predictions / total * 100
    print(f"Acurácia total: {accuracy:.2f}% ({correct_predictions}/{total})")

if __name__ == "__main__":
    while True:
        user_input = input("Digite a descrição do gasto (ou 'testar' para avaliar arquivo, 'sair' para terminar): ")
        if user_input.lower() in ["sair", "exit"]:
            break
        elif user_input.lower() == "testar":
            evaluate_from_file("data/test_data.json", "data/verificacao.json")
        else:
            label, score = classify_text(user_input)
            print(f"Categoria: {label} (confiança={score:.2f})\n")