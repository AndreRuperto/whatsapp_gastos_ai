from open_intent_classifier.model import IntentClassifier
import json

# Carregar o modelo
classifier = IntentClassifier()

# Teste de previsão
test_text = "Almocei em um restaurante perto do trabalho"
prediction = classifier.predict(test_text)

print("📝 Texto:", test_text)
print("📌 Previsão:", prediction)