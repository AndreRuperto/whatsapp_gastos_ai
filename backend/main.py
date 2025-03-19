import logging
from fastapi import FastAPI, Request, Form
import os
import psycopg2
import datetime
import requests
from dotenv import load_dotenv
import json

# Configuração básica de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Carregar variáveis de ambiente
load_dotenv()

app = FastAPI()

# Configuração do Banco de Dados PostgreSQL
DATABASE_URL = os.getenv("DATABASE_URL")
conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

# Criar tabelas caso não existam
cursor.execute('''
    CREATE TABLE IF NOT EXISTS gastos (
        id SERIAL PRIMARY KEY,
        descricao TEXT,
        valor REAL,
        categoria TEXT,
        meio_pagamento TEXT,
        parcelas INT DEFAULT 1,
        data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')
cursor.execute('''
    CREATE TABLE IF NOT EXISTS salario (
        id SERIAL PRIMARY KEY,
        valor REAL,
        data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')
cursor.execute('''
    CREATE TABLE IF NOT EXISTS fatura_cartao (
        id SERIAL PRIMARY KEY,
        valor REAL,
        data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')
conn.commit()
cursor.close()
conn.close()

# URL do WhatsApp Bot (Servidor Node.js)
WHATSAPP_BOT_URL = os.getenv("WHATSAPP_BOT_URL")
API_COTACAO = os.getenv("API_COTACAO", "https://economia.awesomeapi.com.br/json/last/")

with open("backend/data/moedas.json", "r", encoding="utf-8") as file:
    dados_moedas = json.load(file)

MOEDAS = dados_moedas.get("moedas_disponiveis", {})

MOEDA_EMOJIS = {
    "USD": "🇺🇸",
    "EUR": "🇺🇳",
    "GBP": "🏴",
    "BTC": "🪙",
    "ETH": "💎"
}


@app.post("/webhook")
async def receber_mensagem(
    Body: str = Form(...),
    From: str = Form(...)
):
    mensagem = Body.strip()
    telefone = From.replace("whatsapp:", "").replace("+", "")

    logger.info("📩 Mensagem recebida: '%s' de %s", mensagem, telefone)

    # 📌 Comandos Específicos
    if mensagem.lower() == "total gasto no mês?":
        total = calcular_total_gasto()
        resposta = f"📊 Total gasto no mês: R$ {format(total, ',.2f').replace(',', '.')}"
        enviar_mensagem_whatsapp(telefone, resposta)
        return {"status": "OK", "resposta": resposta}

    if "salario" in mensagem.lower():
        status = registrar_salario(mensagem)
        enviar_mensagem_whatsapp(telefone, status["status"])
        return status

    if "fatura" in mensagem.lower():
        status = registrar_fatura_cartao(mensagem)
        enviar_mensagem_whatsapp(telefone, status["status"])
        return status

    if mensagem.lower() == "cotação":
        resposta = obter_cotacao_principais()
        enviar_mensagem_whatsapp(telefone, resposta)
        return {"status": "OK", "resposta": resposta}

    if mensagem.startswith("cotação "):
        moeda = mensagem.split(" ")[1].upper()
        resposta = obter_cotacao(moeda)
        enviar_mensagem_whatsapp(telefone, resposta)
        return {"status": "OK", "resposta": resposta}

    # 📌 Processamento de GASTOS
    logger.info("🔍 Tentando processar mensagem como gasto...")

    descricao, valor, categoria, meio_pagamento, parcelas = processar_mensagem(mensagem)

    # ⚠️ Verificação de erro no processamento
    if descricao == "Erro" or valor == 0.0:
        resposta = "⚠️ Não entendi sua mensagem. Tente informar o gasto no formato: 'Lanche 30' ou 'Uber 25 crédito'."
        enviar_mensagem_whatsapp(telefone, resposta)
        return {"status": "ERRO", "resposta": resposta}

    logger.info(
        "✅ Gasto reconhecido: %s | Valor: %.2f | Categoria: %s | Meio de Pagamento: %s | Parcelas: %d",
        descricao, valor, categoria, meio_pagamento, parcelas
    )

    salvar_gasto(descricao, valor, categoria, meio_pagamento, parcelas)

    resposta = f"✅ Gasto de R$ {format(valor, ',.2f').replace(',', '.')} em '{categoria}' registrado com sucesso!"
    enviar_mensagem_whatsapp(telefone, resposta)
    return {"status": "OK", "resposta": resposta}

def processar_mensagem(mensagem: str):
    """
    Processa a mensagem e extrai descrição, valor, categoria, meio de pagamento e parcelas.
    Inclui logs detalhados para entender cada etapa do parsing.
    """
    try:
        logger.info("📩 Mensagem original recebida (ultima alteração): '%s'", mensagem)
        partes = mensagem.lower().split()
        logger.info("🔎 Mensagem após split: %s", partes)

        valor = 0.0
        meio_pagamento = "Desconhecido"
        parcelas = 1
        descricao = ""

        for i, parte in enumerate(partes):
            logger.info("   - Verificando parte [%d]: '%s'", i, parte)

            if parte.replace(".", "").isdigit():
                valor = float(parte)
                logger.info("   -> Valor numérico encontrado: %.2f", valor)

                # 📌 Detectando parcelamento mesmo que ele venha depois
                if i + 1 < len(partes):
                    logger.info("   📌 Verificando possível parcelamento em: '%s'", partes[i + 1])
                    if partes[i + 1].endswith("x") and partes[i + 1][:-1].isdigit():
                        parcelas = int(partes[i + 1][:-1])
                        logger.info("   ✅ Parcelamento identificado: %dx", parcelas)

                descricao = " ".join(partes[:i])
                logger.info("   -> Descrição identificada: '%s'", descricao)

                # 📌 Detectando meio de pagamento
                if i + 2 < len(partes):
                    logger.info("   📌 Verificando possível meio de pagamento em: '%s'", partes[i + 2])
                    if partes[i + 2] in MEIOS_PAGAMENTO_VALIDOS:
                        meio_pagamento = partes[i + 2]
                        logger.info("   ✅ Meio de pagamento identificado: '%s'", meio_pagamento)

                break  # Interrompe o loop pois o valor já foi encontrado

        if valor == 0.0:
            logger.warning("⚠️ Nenhum valor encontrado na mensagem!")
            return "Erro", 0.0, "Desconhecido", "Desconhecido", 1

        categoria = definir_categoria(descricao)
        logger.info("   -> Categoria definida: '%s'", categoria)

        return descricao.strip(), valor, categoria, meio_pagamento, parcelas

    except Exception as e:
        logger.exception("❌ Erro ao processar mensagem:")
        return "Erro", 0.0, "Desconhecido", "Desconhecido", 1

MEIOS_PAGAMENTO_VALIDOS = ["pix", "crédito", "débito"]

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


def salvar_gasto(descricao, valor, categoria, meio_pagamento, parcelas):
    """
    Salva o gasto no banco de dados PostgreSQL.
    """
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    for i in range(parcelas):
        data = datetime.datetime.now() + datetime.timedelta(days=30 * i)
        cursor.execute(
            "INSERT INTO gastos (descricao, valor, categoria, meio_pagamento, parcelas, data) VALUES (%s, %s, %s, %s, %s, %s)",
            (descricao, valor / parcelas, categoria, meio_pagamento, parcelas, data)
        )

    conn.commit()
    cursor.close()
    conn.close()


def calcular_total_gasto():
    """
    Calcula o total gasto no mês atual.
    """
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute("SELECT SUM(valor) FROM gastos WHERE data >= date_trunc('month', CURRENT_DATE)")
    total = cursor.fetchone()[0] or 0.0
    cursor.close()
    conn.close()
    return total


def registrar_salario(mensagem):
    """
    Registra um novo salário no banco de dados.
    """
    try:
        valor = float(mensagem.split()[-1])
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO salario (valor) VALUES (%s)", (valor,))
        conn.commit()
        cursor.close()
        conn.close()
        return {"status": "💰 Salário registrado com sucesso!"}
    except:
        logger.exception("❌ Erro ao registrar salário:")
        return {"status": "❌ Erro ao registrar salário"}


def registrar_fatura_cartao(mensagem):
    """
    Registra o valor da fatura do cartão.
    """
    try:
        valor = float(mensagem.split()[-1])
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO fatura_cartao (valor) VALUES (%s)", (valor,))
        conn.commit()
        cursor.close()
        conn.close()
        return {"status": "💳 Fatura do cartão registrada com sucesso!"}
    except:
        logger.exception("❌ Erro ao registrar fatura:")
        return {"status": "❌ Erro ao registrar fatura"}


def obter_cotacao_principais():
    """
    Obtém as cotações das 5 principais moedas (USD, EUR, GBP, BTC, ETH).
    """
    moedas = ["USD", "EUR", "GBP", "BTC", "ETH"]
    url = f"{API_COTACAO}" + ",".join([f"{m}-BRL" for m in moedas])
    logger.info("📡 Buscando cotações na URL: %s", url)

    try:
        response = requests.get(url)
        data = response.json()
        logger.info("📊 Dados recebidos: %s", data)

        cotacoes = []
        for moeda in moedas:
            key = f"{moeda}BRL"
            if key in data:
                valor = float(data[key]['bid'])
                emoji = MOEDA_EMOJIS.get(moeda, "💰")
                valor_formatado = f"R$ {format(valor, ',.2f').replace(',', '.')}"
                cotacoes.append(f"{emoji} {moeda}: {valor_formatado}")

        if not cotacoes:
            return "⚠️ Nenhuma cotação encontrada. Verifique a API."

        return "📈 Cotações principais:\n\n" + "\n".join(cotacoes)

    except Exception as e:
        logger.exception("❌ Erro ao buscar cotações:")
        return f"❌ Erro ao buscar cotações: {str(e)}"


def obter_cotacao(moeda: str):
    """
    Obtém a cotação da moeda informada e retorna o nome da moeda.
    """
    moeda = moeda.upper()
    nome_moeda = MOEDAS.get(moeda, "Moeda não encontrada")

    try:
        response = requests.get(f"https://economia.awesomeapi.com.br/json/last/{moeda}-BRL")
        data = response.json()
        key = f"{moeda}BRL"

        if key in data:
            valor = float(data[key]['bid'])
            return f"💰 {nome_moeda} ({moeda}/BRL): R${valor:.2f}"
        else:
            return "⚠️ Moeda não encontrada. Use códigos como USD, EUR, BTC..."
    except Exception as e:
        logger.exception("❌ Erro ao buscar cotação:")
        return f"❌ Erro ao buscar cotação: {str(e)}"


def enviar_mensagem_whatsapp(telefone, mensagem):
    logger = logging.getLogger(__name__)
    
    logger.info("Telefone original recebido: %s", telefone)

    numero_limpo = telefone.replace("whatsapp:", "").replace("+", "")
    logger.info("Após remover 'whatsapp:' e '+': %s", numero_limpo)

    # Se ainda terminar com '@c.us', removemos
    if numero_limpo.endswith("@c.us"):
        logger.info("O número termina com '@c.us'. Removendo sufixo...")
        numero_limpo = numero_limpo[:-5]  # remove os últimos 5 caracteres
    else:
        logger.info("O número não termina com '@c.us'. Nada a remover.")

    logger.info("Número final (limpo): %s", numero_limpo)

    payload = {
        "number": numero_limpo,  # ex.: "556199570838"
        "message": mensagem
    }
    logger.info("Payload final a ser enviado: %s", payload)

    try:
        response = requests.post(WHATSAPP_BOT_URL, json=payload)
        logger.info("Resposta do POST status code: %d", response.status_code)
        response.raise_for_status()
        return {"status": "Mensagem enviada"}
    except requests.exceptions.RequestException as e:
        logger.exception("❌ Erro ao enviar mensagem via WhatsApp:")
        return {"status": "Erro ao enviar mensagem", "error": str(e)}