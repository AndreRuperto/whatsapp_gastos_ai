import fasttext

# Carregar o modelo treinado
modelo = fasttext.load_model("modelo_gastos_fasttext.bin")

# Frases complexas para teste
descricoes_teste = [
    "Abastecimento de combustível do carro, gasolina aditivada no posto Shell.",
    "Almoço executivo no restaurante italiano, com bebida inclusa e sobremesa.",
    "Mensalidade da academia, plano anual com acesso ilimitado a todas as unidades.",
    "Consulta veterinária para vacinação anual do cachorro, com remédio antipulgas.",
    "Compra de notebook gamer com placa de vídeo dedicada para trabalho e jogos."
]

for descricao in descricoes_teste:
    predicao = modelo.predict(descricao)
    categoria_predita = predicao[0][0].replace('__label__', '')
    probabilidade = predicao[1][0]

    print(f"🔮 Descrição: {descricao}")
    print(f"➡️ Categoria prevista: {categoria_predita} ({probabilidade:.2%})")
    print("-" * 80)