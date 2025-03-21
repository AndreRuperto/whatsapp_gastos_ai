import logging
from fastapi import FastAPI, Request, Form
import os
import psycopg2
import datetime
import requests
from dotenv import load_dotenv

from backend.services.scheduler import scheduler
from backend.services.whatsapp_service import enviar_mensagem_whatsapp
from backend.services.db_init import inicializar_bd

from backend.services.cotacao_service import (
    obter_cotacao_principais, obter_cotacao
)

from backend.services.gastos_service import (
    salvar_gasto, salvar_fatura, calcular_total_gasto, pagar_fatura, registrar_salario
)

# Configuração básica de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Carregar variáveis de ambiente
load_dotenv()

app = FastAPI()

DATABASE_URL = os.getenv("DATABASE_URL")
inicializar_bd(DATABASE_URL)

@app.post("/webhook")
async def receber_mensagem(Body: str = Form(...), From: str = Form(...)):
    mensagem = Body.strip()
    telefone = From.replace("whatsapp:", "").replace("+", "")

    logger.info("📩 Mensagem recebida: '%s' de %s", mensagem, telefone)

    # 📌 Comandos específicos
    if mensagem.lower() == "total gasto no mês?":
        total = calcular_total_gasto()
        resposta = f"📊 Total gasto no mês: R$ {format(total, ',.2f').replace(',', '.')}"
        enviar_mensagem_whatsapp(telefone, resposta)
        return {"status": "OK", "resposta": resposta}

    if mensagem.lower() == "fatura paga!":
        pagar_fatura()
        resposta = "✅ Todas as compras parceladas deste mês foram adicionadas ao total de gastos!"
        enviar_mensagem_whatsapp(telefone, resposta)
        return {"status": "OK", "resposta": resposta}

    # 📌 Processamento de gastos
    logger.info("🔍 Tentando processar mensagem como gasto...")
    
    descricao, valor, categoria, meio_pagamento, parcelas = processar_mensagem(mensagem)

    if descricao == "Erro" or valor == 0.0:
        resposta = "⚠️ Não entendi sua mensagem. Tente informar o gasto no formato: 'Lanche 30' ou 'Uber 25 crédito'."
        enviar_mensagem_whatsapp(telefone, resposta)
        return {"status": "ERRO", "resposta": resposta}

    logger.info(
        "✅ Gasto reconhecido: %s | Valor: %.2f | Categoria: %s | Meio de Pagamento: %s | Parcelas: %d",
        descricao, valor, categoria, meio_pagamento, parcelas
    )

    # Salva o gasto
    salvar_gasto(descricao, valor, categoria, meio_pagamento, parcelas)

    if meio_pagamento in ["pix", "débito"]:
        resposta = f"✅ Gasto de R$ {format(valor, ',.2f').replace(',', '.')} em '{categoria}' registrado com sucesso!"
    else:
        resposta = f"✅ Compra parcelada registrada! {parcelas}x de R$ {valor/parcelas:.2f}"

    enviar_mensagem_whatsapp(telefone, resposta)
    return {"status": "OK", "resposta": resposta}


def processar_mensagem(mensagem: str):
    """
    Processa a mensagem e extrai descrição, valor, categoria, meio de pagamento e parcelas.
    """
    try:
        logger.info("📩 Mensagem original recebida: '%s'", mensagem)
        partes = mensagem.lower().split()
        logger.info("🔎 Mensagem após split: %s", partes)

        valor = 0.0
        meio_pagamento = "Desconhecido"
        parcelas = 1
        descricao = ""

        for i, parte in enumerate(partes):
            if parte.replace(".", "").isdigit():
                valor = float(parte)
                descricao = " ".join(partes[:i])

                # 📌 Detectando parcelamento
                if i + 1 < len(partes) and partes[i + 1].endswith("x") and partes[i + 1][:-1].isdigit():
                    parcelas = int(partes[i + 1][:-1])

                # 📌 Detectando meio de pagamento
                if i + 2 < len(partes) and partes[i + 2] in ["pix", "crédito", "débito"]:
                    meio_pagamento = partes[i + 2]

                break  # Paramos após encontrar o valor

        if valor == 0.0:
            logger.warning("⚠️ Nenhum valor encontrado na mensagem!")
            return "Erro", 0.0, "Desconhecido", "Desconhecido", 1

        categoria = definir_categoria(descricao)
        return descricao.strip(), valor, categoria, meio_pagamento, parcelas

    except Exception as e:
        logger.exception("❌ Erro ao processar mensagem:")
        return "Erro", 0.0, "Desconhecido", "Desconhecido", 1

def definir_categoria(descricao: str):
    """
    Seu dicionário de categorias, com palavras-chave.
    """
    categorias = {
        # 🍽️ Alimentação
        "almoço": "Alimentação",
        "jantar": "Alimentação",
        "café": "Alimentação",
        "lanchonete": "Alimentação",
        "pizza": "Alimentação",
        "hamburguer": "Alimentação",
        "churrasco": "Alimentação",
        "restaurante": "Alimentação",
        "delivery": "Alimentação",
        "sushi": "Alimentação",
        "padaria": "Alimentação",
        "bar": "Alimentação",
        "fast food": "Alimentação",
        "marmita": "Alimentação",
        "doceria": "Alimentação",
        "brigadeiro": "Alimentação",
        "chocolate": "Alimentação",
        "brownie": "Alimentação",
        "festival gastronômico": "Alimentação",
        "rodízio": "Alimentação",
        "buffet": "Alimentação",
        "petiscos": "Alimentação",
        "food truck": "Alimentação",
        "vinho": "Alimentação",
        "cerveja": "Alimentação",
        "bebidas": "Alimentação",
        "feijoada": "Alimentação",
        "coxinha": "Alimentação",
        "esfiha": "Alimentação",
        "pastel": "Alimentação",
        "salgado": "Alimentação",
        "tapioca": "Alimentação",
        "sorvete": "Alimentação",
        "gelato": "Alimentação",
        "milkshake": "Alimentação",
        "cupcake": "Alimentação",

        # 🚗 Transporte
        "uber": "Transporte",
        "99": "Transporte",
        "ônibus": "Transporte",
        "metrô": "Transporte",
        "trem": "Transporte",
        "gasolina": "Transporte",
        "estacionamento": "Transporte",
        "pedágio": "Transporte",
        "bike": "Transporte",
        "patinete": "Transporte",
        "carro": "Transporte",
        "manutenção carro": "Transporte",
        "reboque": "Transporte",
        "taxi": "Transporte",
        "mototáxi": "Transporte",
        "passagem": "Transporte",
        "aéreo": "Transporte",
        "uber eats": "Transporte",
        "combustível": "Transporte",
        "lava rápido": "Transporte",

        # 🏠 Moradia
        "aluguel": "Moradia",
        "condomínio": "Moradia",
        "iptu": "Moradia",
        "seguro residencial": "Moradia",
        "faxina": "Moradia",
        "reforma": "Moradia",
        "móvel": "Moradia",
        "imobiliária": "Moradia",
        "decoração": "Moradia",
        "mudança": "Moradia",
        "pintura": "Moradia",
        "limpeza": "Moradia",
        "síndico": "Moradia",
        "guarita": "Moradia",
        "porteiro": "Moradia",
        "manutenção casa": "Moradia",
        "jardinagem": "Moradia",
        "ar condicionado": "Moradia",
        "gás encanado": "Moradia",
        "portão": "Moradia",

        # 🔌 Contas e Serviços Públicos
        "luz": "Contas",
        "água": "Contas",
        "internet": "Contas",
        "celular": "Contas",
        "tv a cabo": "Contas",
        "telefonia": "Contas",
        "taxa lixo": "Contas",
        "energia": "Contas",
        "iluminação": "Contas",
        "esgoto": "Contas",
        "contador": "Contas",
        "ipva": "Contas",
        "dpvat": "Contas",
        "licenciamento": "Contas",
        "multas": "Contas",

        # 🛒 Supermercado
        "mercado": "Supermercado",
        "compras": "Supermercado",
        "hortifruti": "Supermercado",
        "açougue": "Supermercado",
        "feira": "Supermercado",
        "peixaria": "Supermercado",
        "frios": "Supermercado",
        "mercearia": "Supermercado",
        "limpeza": "Supermercado",
        "higiene": "Supermercado",
        "perfumaria": "Supermercado",
        "empório": "Supermercado",
        "hipermercado": "Supermercado",
        "suprimentos": "Supermercado",
        "armazém": "Supermercado",

        # 🎭 Lazer e Entretenimento
        "cinema": "Lazer",
        "show": "Lazer",
        "teatro": "Lazer",
        "netflix": "Lazer",
        "spotify": "Lazer",
        "prime video": "Lazer",
        "disney+": "Lazer",
        "xbox game pass": "Lazer",
        "playstation plus": "Lazer",
        "steam": "Lazer",
        "livro": "Lazer",
        "parque": "Lazer",
        "passeio": "Lazer",
        "viagem": "Lazer",
        "ingresso": "Lazer",

        # 🏥 Saúde
        "farmácia": "Saúde",
        "remédio": "Saúde",
        "médico": "Saúde",
        "dentista": "Saúde",
        "hospital": "Saúde",
        "exame": "Saúde",
        "academia": "Saúde",
        "pilates": "Saúde",
        "fisioterapia": "Saúde",
        "nutricionista": "Saúde",
        "psicólogo": "Saúde",
        "massagem": "Saúde",
        "terapia": "Saúde",
        "plano de saúde": "Saúde",
        "suplemento": "Saúde",
        "vacina": "Saúde",
        "óculos": "Saúde",
        "lente de contato": "Saúde",
        "cirurgia": "Saúde",
        "bem-estar": "Saúde",

        # 🎓 Educação
        "faculdade": "Educação",
        "curso": "Educação",
        "apostila": "Educação",
        "plataforma educacional": "Educação",
        "mentoria": "Educação",
        "workshop": "Educação",
        "palestra": "Educação",
        "treinamento": "Educação",
        "aula particular": "Educação",
        "material escolar": "Educação",

        # 💻 Tecnologia
        "notebook": "Tecnologia",
        "computador": "Tecnologia",
        "fones de ouvido": "Tecnologia",
        "mouse": "Tecnologia",
        "teclado": "Tecnologia",
        "tablet": "Tecnologia",
        "monitor": "Tecnologia",
        "ssd": "Tecnologia",
        "pendrive": "Tecnologia",
        "cabo usb": "Tecnologia",
        "hd externo": "Tecnologia",
        "streaming": "Tecnologia",
        "smartphone": "Tecnologia",
        "console": "Tecnologia",
        "carregador": "Tecnologia",

        # 👗 Vestuário
        "roupa": "Vestuário",
        "tênis": "Vestuário",
        "calçado": "Vestuário",
        "camiseta": "Vestuário",
        "calça": "Vestuário",
        "blusa": "Vestuário",
        "moletom": "Vestuário",
        "casaco": "Vestuário",
        "acessórios": "Vestuário",
        "joias": "Vestuário",
        "mala": "Vestuário",
        "bolsa": "Vestuário",
        "meias": "Vestuário",
        "cinto": "Vestuário",
        "biquíni": "Vestuário",

        # 🎁 Presentes
        "presente": "Presentes",
        "lembrancinha": "Presentes",
        "aniversário": "Presentes",
        "casamento": "Presentes",
        "amigo secreto": "Presentes",
        "mimo": "Presentes",

        # ❤️ Doações
        "doação": "Doações",
        "vaquinha": "Doações",
        "ong": "Doações",
        "ajuda": "Doações",
        "solidariedade": "Doações",

        # 💰 Finanças
        "investimento": "Finanças",
        "poupança": "Finanças",
        "cartão de crédito": "Finanças",
        "empréstimo": "Finanças",
        "seguro": "Finanças",
        "juros": "Finanças",
        "financiamento": "Finanças",
        "consórcio": "Finanças",
        "aplicação": "Finanças",
        "corretora": "Finanças",

        # ⚙️ Serviços
        "barbearia": "Serviços",
        "cabeleireiro": "Serviços",
        "manicure": "Serviços",
        "estética": "Serviços",
        "encanador": "Serviços",
        "eletricista": "Serviços",
        "reparo": "Serviços",
        "fotografia": "Serviços",
        "freelancer": "Serviços",
        "tradução": "Serviços",
        "lavanderia": "Serviços",
        "pet shop": "Serviços",
        "faxineira": "Serviços",
        "costureira": "Serviços",
        "carpintaria": "Serviços",

        # 📦 Assinaturas
        "revista": "Assinaturas",
        "jornal": "Assinaturas",
        "plano anual": "Assinaturas",
        "mensalidade": "Assinaturas",
        "patreon": "Assinaturas",
        "apoia.se": "Assinaturas",
        "twitch sub": "Assinaturas",
        "club de assinatura": "Assinaturas",
        "newsletter paga": "Assinaturas",
        "finclass": "Assinaturas",

        # 🐱 Pets
        "ração": "Pets",
        "petisco": "Pets",
        "veterinário": "Pets",
        "vacina pet": "Pets",
        "casinha": "Pets",
        "areia": "Pets",
        "banho e tosa": "Pets",
        "coleira": "Pets",
        "brinquedo pet": "Pets",
        "remédio pet": "Pets",

        # 🛠️ Hobby & DIY
        "ferramenta": "Hobby/DIY",
        "madeira": "Hobby/DIY",
        "tinta spray": "Hobby/DIY",
        "cola quente": "Hobby/DIY",
        "artesanato": "Hobby/DIY",
        "bordado": "Hobby/DIY",
        "tricot": "Hobby/DIY",
        "crochê": "Hobby/DIY",

        # 🌱 Jardinagem
        "mudas": "Jardinagem",
        "adubo": "Jardinagem",
        "fertilizante": "Jardinagem",
        "vaso": "Jardinagem",
        "regador": "Jardinagem",
    }

    # Percorre o dicionário e verifica se a palavra-chave está na descrição
    for chave, cat in categorias.items():
        if chave in descricao.lower():
            return cat
    return "Outros"