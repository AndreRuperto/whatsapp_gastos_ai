import json
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import classification_report, confusion_matrix
import pandas as pd

# Carregar os arquivos de teste e verificação
with open("data/test_data.json", "r", encoding="utf-8") as f:
    test_data = json.load(f)

with open("verificacao.json", "r", encoding="utf-8") as f:
    verification_data = json.load(f)

# Criar listas para análise
true_labels = []
predicted_labels = []

# Simular a predição (já gerada anteriormente)
for test_item, verification_item in zip(test_data, verification_data):
    predicted_labels.append(test_item.get("predicted", ""))  # Supondo que "predicted" esteja armazenado no JSON de saída
    true_labels.append(verification_item["categoria"])

# Gerar relatório de classificação
report = classification_report(true_labels, predicted_labels, output_dict=True)
df_report = pd.DataFrame(report).transpose()

# Criar matriz de confusão
conf_matrix = confusion_matrix(true_labels, predicted_labels, labels=list(set(true_labels)))

# Exibir relatório
tools.display_dataframe_to_user(name="Relatório de Classificação", dataframe=df_report)

# Plotar matriz de confusão
plt.figure(figsize=(12, 8))
sns.heatmap(conf_matrix, annot=True, fmt="d", cmap="Blues", xticklabels=list(set(true_labels)), yticklabels=list(set(true_labels)))
plt.xlabel("Predito")
plt.ylabel("Real")
plt.title("Matriz de Confusão")
plt.show()