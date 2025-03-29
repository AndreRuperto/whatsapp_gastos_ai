import fasttext
import fasttext.util

# fasttext.util.download_model('pt', if_exists='ignore')
# ft = fasttext.load_model('cc.pt.300.bin')
# print(ft.get_sentence_vector("teste"))

# Treinando o modelo com o arquivo gerado
modelo = fasttext.train_supervised("dados_fasttext.txt", epoch=30, lr=1.0)

# Salvar o modelo treinado
modelo.save_model("modelo_gastos_fasttext.bin")

print("✅ Modelo treinado e salvo com sucesso!")
