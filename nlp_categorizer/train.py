import json
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report

# Carregar os dados do arquivo JSON
with open("data/train_data_oic.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# Converter para DataFrame
df = pd.DataFrame(data)

# Separar dados e rótulos
X = df["text"]
y = df["intent"]

# Separar em treino e teste
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Criar pipeline com TF-IDF + Classificador
pipeline = Pipeline([
    ("tfidf", TfidfVectorizer()),
    ("clf", LogisticRegression(max_iter=1000))
])

# Treinar modelo
pipeline.fit(X_train, y_train)

# Avaliar modelo
y_pred = pipeline.predict(X_test)
relatorio = classification_report(y_test, y_pred, output_dict=True)

import matplotlib.pyplot as plt
import seaborn as sns

# Mostrar matriz de confusão como exemplo de visualização
from sklearn.metrics import confusion_matrix

conf_matrix = confusion_matrix(y_test, y_pred, labels=pipeline.classes_)
conf_df = pd.DataFrame(conf_matrix, index=pipeline.classes_, columns=pipeline.classes_)

import seaborn as sns
import matplotlib.pyplot as plt
import io

# Criar figura
plt.figure(figsize=(12, 10))
sns.heatmap(conf_df, annot=True, fmt="d", cmap="Blues")
plt.title("Matriz de Confusão por Categoria")
plt.ylabel("Real")
plt.xlabel("Previsto")
plt.tight_layout()

# Salvar imagem
image_path = "data/matriz_confusao.png"
plt.savefig(image_path)
plt.close()

# Exibir uma previsão de exemplo
exemplo = "Uber 40"
pred_exemplo = pipeline.predict([exemplo])[0]

# Retornar informações para o usuário
relatorio_geral = classification_report(y_test, y_pred)

(image_path, exemplo, pred_exemplo, relatorio_geral)
