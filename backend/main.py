import logging
from fastapi import FastAPI, Request, Form
import os
import psycopg2
import datetime
import requests
from dotenv import load_dotenv
import json
from fastapi.responses import PlainTextResponse, JSONResponse
import time
from datetime import datetime
import re

from backend.services.scheduler import scheduler, agendar_lembrete_cron
from backend.services.whatsapp_service import enviar_mensagem_whatsapp
from backend.services.db_init import inicializar_bd

from backend.services.cotacao_service import (
    obter_cotacao_principais, obter_cotacao, MOEDAS, MOEDA_EMOJIS
)

from backend.services.gastos_service import (
    salvar_gasto, salvar_fatura, calcular_total_gasto, pagar_fatura, registrar_salario, mensagem_ja_processada, registrar_mensagem_recebida 
)

# Configuração básica de logging
LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "app.log"), encoding="utf-8"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Carregar variáveis de ambiente
load_dotenv()

app = FastAPI()

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
API_COTACAO = os.getenv("API_COTACAO")
inicializar_bd(DATABASE_URL)

@app.get("/ping")
def ping():
    return {"status": "alive!"}

@app.get("/debug") # Usado para verificação inicial da Meta
async def verify(request: Request):
    params = dict(request.query_params)
    if params.get("hub.mode") == "subscribe" and params.get("hub.verify_token") == VERIFY_TOKEN:
        return PlainTextResponse(content=params["hub.challenge"])
    return {"status": "erro", "mensagem": "Token inválido."}

@app.post("/debug")
async def debug_route(request: Request):
    # Lê o corpo da requisição como JSON
    data = await request.json()
    
    # Exibe (print) no console -- mas lembre que em producao
    # o "print" pode não ser visível. 
    print("DEBUG - Corpo da requisição:", data)
    
    # Também podemos logar com o logger para aparecer no Railway Deploy Logs
    logger.info(f"DEBUG - Corpo da requisição: {data}")
    
    # Retorna uma resposta simples, confirmando que recebeu o JSON
    return {"status": "ok", "received_data": data}

@app.get("/webhook") # Usado para verificação inicial da Meta
async def verify(request: Request):
    params = dict(request.query_params)
    if params.get("hub.mode") == "subscribe" and params.get("hub.verify_token") == VERIFY_TOKEN:
        return PlainTextResponse(content=params["hub.challenge"])
    return {"status": "erro", "mensagem": "Token inválido."}

@app.post("/webhook")
async def receber_mensagem(request: Request):
    inicio = time.time()
    logger.info("🔥 Recebi algo no webhook!")

    try:
        dados = await request.json()
        logger.info("📩 Payload recebido: %s", json.dumps(dados, indent=2))
    except Exception as e:
        body = await request.body()
        logger.error("❌ Erro ao decodificar JSON: %s", str(e))
        logger.error("📦 Corpo bruto recebido: %s", body.decode("utf-8"))
        return JSONResponse(content={"status": "erro", "mensagem": "Payload inválido."}, status_code=400)

    try:
        mensagens = dados["entry"][0]["changes"][0]["value"].get("messages", [])
        if not mensagens:
            return JSONResponse(content={"status": "ignorado", "mensagem": "Nenhuma mensagem nova."}, status_code=200)

        mensagem_obj = mensagens[0]
        mensagem = mensagem_obj["text"]["body"].strip()
        mensagem_lower = mensagem.lower()
        telefone = mensagem_obj["from"]
        mensagem_id = mensagem_obj["id"]
        timestamp_whatsapp = int(mensagem_obj["timestamp"])

        logger.info("📩 Mensagem recebida: '%s' de %s", mensagem, telefone)

        # ✅ Verifica se essa mensagem já foi processada
        from backend.services.gastos_service import mensagem_ja_processada, registrar_mensagem_recebida

        if mensagem_ja_processada(mensagem_id):
            logger.warning("⚠️ Mensagem já processada anteriormente: %s", mensagem_id)
            return JSONResponse(content={"status": "ignorado", "mensagem": "Mensagem duplicada ignorada."}, status_code=200)

        registrar_mensagem_recebida(mensagem_id)

        if mensagem_lower == "total gasto no mês?":
            total = calcular_total_gasto()
            resposta = f"📊 Total gasto no mês: R$ {format(total, ',.2f').replace(',', '.')}"
            await enviar_mensagem_whatsapp(telefone, resposta)
            log_tempos(inicio, timestamp_whatsapp, logger, mensagem, telefone)
            return {"status": "OK", "resposta": resposta}

        if mensagem_lower == "fatura paga!":
            pagar_fatura()
            resposta = "✅ Todas as compras parceladas deste mês foram adicionadas ao total de gastos!"
            await enviar_mensagem_whatsapp(telefone, resposta)
            log_tempos(inicio, timestamp_whatsapp, logger, mensagem, telefone)
            return {"status": "OK", "resposta": resposta}

        if mensagem_lower == "cotação":
            resposta = obter_cotacao_principais(API_COTACAO, MOEDA_EMOJIS)
            await enviar_mensagem_whatsapp(telefone, resposta)
            log_tempos(inicio, timestamp_whatsapp, logger, mensagem, telefone)
            return {"status": "OK", "resposta": resposta}

        partes = mensagem.split()
        if len(partes) > 1 and partes[0].lower() == "cotação":
            moeda = partes[1].upper()
            resposta = obter_cotacao(API_COTACAO, moeda, MOEDAS)
            await enviar_mensagem_whatsapp(telefone, resposta)
            log_tempos(inicio, timestamp_whatsapp, logger, mensagem, telefone)
            return {"status": "OK", "resposta": resposta}

        if mensagem_lower.startswith("lembrete:") and "cron:" in mensagem_lower:
            resposta = processar_lembrete_formatado(mensagem, telefone)
            if resposta:
                await enviar_mensagem_whatsapp(telefone, resposta)
                return {"status": "ok"}

        if "tabela de cron" in mensagem_lower:
            tabela = (
                "⏰ Exemplos de expressões CRON:\n"
                "\n* * * * * → Executa a cada minuto\n"
                "0 9 * * * → Todos os dias às 09:00\n"
                "30 14 * * * → Todos os dias às 14:30\n"
                "0 8 * * 1-5 → Segunda a sexta às 08:00\n"
                "15 10 15 * * → Dia 15 de cada mês às 10:15\n"
                "0 0 1 1 * → 1º de janeiro à meia-noite\n"
                "0 18 * * 6 → Todos os sábados às 18:00\n"
                "\nFormato: minuto hora dia_do_mes mês dia_da_semana"
            )
            await enviar_mensagem_whatsapp(telefone, tabela)
            return {"status": "ok"}

        # 📌 Processamento de gastos
        logger.info("🔍 Tentando processar mensagem como gasto...")
        descricao, valor, categoria, meio_pagamento, parcelas = processar_mensagem(mensagem)

        if descricao == "Erro" or valor == 0.0:
            resposta = "⚠️ Não entendi sua mensagem. Tente informar o gasto no formato: 'Lanche 30' ou 'Uber 25 crédito'."
            await enviar_mensagem_whatsapp(telefone, resposta)
            log_tempos(inicio, timestamp_whatsapp, logger, mensagem, telefone)
            return {"status": "ERRO", "resposta": resposta}

        logger.info(
            "✅ Gasto reconhecido: %s | Valor: %.2f | Categoria: %s | Meio de Pagamento: %s | Parcelas: %d",
            descricao, valor, categoria, meio_pagamento, parcelas
        )

        if meio_pagamento in ["pix", "débito"]:
            salvar_gasto(descricao, valor, categoria, meio_pagamento, parcelas)
            resposta = f"✅ Gasto de R$ {format(valor, ',.2f').replace(',', '.')} em '{categoria}' registrado com sucesso!"
        else:
            salvar_fatura(descricao, valor, categoria, meio_pagamento, parcelas)
            resposta = f"✅ Compra parcelada registrada! {parcelas}x de R$ {valor/parcelas:.2f}"

        await enviar_mensagem_whatsapp(telefone, resposta)
        log_tempos(inicio, timestamp_whatsapp, logger, mensagem, telefone)
        return {"status": "OK", "resposta": resposta}

    except Exception as e:
        logger.exception("❌ Erro ao processar webhook:")
        return JSONResponse(content={"status": "erro", "mensagem": str(e)}, status_code=500)

def descrever_cron_humanamente(expr):
    minutos, hora, dia, mes, semana = expr.strip().split()
    partes = []

    dias_semana = {
        "0": "domingo",
        "1": "segunda-feira",
        "2": "terça-feira",
        "3": "quarta-feira",
        "4": "quinta-feira",
        "5": "sexta-feira",
        "6": "sábado"
    }

    if semana == "*":
        partes.append("todos os dias")
    elif semana in dias_semana:
        partes.append(f"aos {dias_semana[semana]}")
    elif semana == "1-5":
        partes.append("de segunda a sexta-feira")
    elif semana == "0,6":
        partes.append("aos fins de semana")
    elif "," in semana:
        dias = [dias_semana.get(d, d) for d in semana.split(",")]
        partes.append("aos " + ", ".join(dias))
    else:
        partes.append(f"nos dias da semana: {semana}")

    if dia != "*":
        partes.append(f"no dia {dia}")

    if mes != "*":
        partes.append(f"em {mes}")

    partes.append(f"\u00e0s {hora.zfill(2)}h{minutos.zfill(2)}")
    return " ".join(partes)


def processar_lembrete_formatado(mensagem: str, telefone: str):

    padrao = r'lembrete:\s*"(.+?)"\s*cron:\s*([0-9*/,\- ]{5,})'
    match = re.search(padrao, mensagem.lower())
    if match:
        lembrete_texto = match.group(1).strip()
        cron_expr = match.group(2).strip()
        agendar_lembrete_cron(telefone, lembrete_texto, cron_expr)
        descricao = descrever_cron_humanamente(cron_expr)
        return f"\u23f0 Lembrete agendado com sucesso!\nMensagem: \"{lembrete_texto}\"\nQuando: {descricao}"
    return None
    
def log_tempos(inicio: float, timestamp_whatsapp: int, logger, mensagem: str, telefone: str):
    fim = time.time()
    horario_whatsapp = datetime.fromtimestamp(timestamp_whatsapp).strftime('%Y-%m-%d %H:%M:%S')
    horario_servidor = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    logger.info("📩 Mensagem recebida: '%s' de %s", mensagem, telefone)
    logger.info("⏱️ Timestamp WhatsApp: %s", horario_whatsapp)
    logger.info("🕒 Timestamp do servidor: %s", horario_servidor)
    logger.info("⚡ Tempo total de resposta: %.2f segundos", fim - inicio)

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

                # 📌 Detectando parcelamento (Ex: "3x crédito")
                if i + 1 < len(partes) and partes[i + 1].endswith("x") and partes[i + 1][:-1].isdigit():
                    parcelas = int(partes[i + 1][:-1])
                    i += 1  # Avançar para evitar erro

                # 📌 Detectando meio de pagamento (Ex: "crédito", "débito", "pix")
                if i + 1 < len(partes) and partes[i + 1] in ["pix", "crédito", "débito"]:
                    meio_pagamento = partes[i + 1]

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