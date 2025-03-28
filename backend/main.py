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

from backend.services.api_service import (
    obter_cotacao_principais, obter_cotacao, buscar_cep, listar_moedas_disponiveis, listar_conversoes_disponiveis, listar_conversoes_disponiveis_moeda, MOEDAS, CONVERSOES, MOEDA_EMOJIS
)

from backend.services.gastos_service import (
    salvar_gasto, salvar_fatura, calcular_total_gasto, pagar_fatura, registrar_salario, mensagem_ja_processada, registrar_mensagem_recebida, listar_lembretes, apagar_lembrete
)

from backend.services.autorizacao_service import verificar_autorizacao, liberar_usuario
from backend.services.usuarios_service import listar_usuarios_autorizados, revogar_autorizacao
from backend.services.token_service import gerar_token_acesso

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

        # 🛡️ Proteção contra mensagens sem campo 'text'
        try:
            mensagem = mensagem_obj["text"]["body"].strip()
        except KeyError:
            tipo_mensagem = mensagem_obj.get("type", "desconhecido")
            telefone = mensagem_obj.get("from", "desconhecido")
            logger.warning(f"⚠️ Mensagem sem campo 'text'. Tipo: {tipo_mensagem}")
            logger.warning(f"📦 Conteúdo bruto da mensagem: {json.dumps(mensagem_obj, indent=2)}")
            await enviar_mensagem_whatsapp(
                telefone,
                "🚫 Sua mensagem não pôde ser processada. Envie um texto simples como 'oi' ou 'cotação'."
            )
            return JSONResponse(
                content={"status": "ignorado", "mensagem": "Tipo de mensagem não suportado"},
                status_code=200
            )

        mensagem_lower = mensagem.lower()
        telefone = mensagem_obj["from"]
        mensagem_id = mensagem_obj["id"]
        timestamp_whatsapp = int(mensagem_obj["timestamp"])

        logger.info("📩 Mensagem recebida: '%s' de %s", mensagem, telefone)

        if not verificar_autorizacao(telefone):
            logger.warning("🔒 Número não autorizado: %s", telefone)

            # Envia notificação ao ADMIN
            admin = os.getenv("ADMIN_PHONE")
            texto_admin = f"🔐 Solicitação de acesso de um novo número:\n{telefone}\n\nDeseja liberar com:\nliberar {telefone}"
            await enviar_mensagem_whatsapp(admin, texto_admin)

            # Informa ao usuário
            texto_usuario = "🚫 Seu número ainda não está autorizado a usar o assistente financeiro. Aguarde a liberação."
            await enviar_mensagem_whatsapp(telefone, texto_usuario)

            return JSONResponse(content={"status": "bloqueado", "mensagem": "Número não autorizado"}, status_code=200)

        # 🔍 Obtém o schema associado ao telefone
        schema = obter_schema_por_telefone(telefone)
        if not schema:
            logger.error(f"⚠️ Usuário {telefone} sem schema autorizado.")
            return JSONResponse(content={"status": "erro", "mensagem": "Usuário não possui schema vinculado."}, status_code=403)
        
        if mensagem_ja_processada(mensagem_id):
            logger.warning("⚠️ Mensagem já processada anteriormente: %s", mensagem_id)
            return JSONResponse(content={"status": "ignorado", "mensagem": "Mensagem duplicada ignorada."}, status_code=200)

        registrar_mensagem_recebida(mensagem_id)

        partes = mensagem.split()
        if mensagem_lower in ["ajuda", "menu", "comandos"]:
            await exibir_menu_ajuda(telefone)
            return {"status": "OK", "resposta": "Menu de ajuda enviado"}

        elif mensagem_lower == "total gasto":
            total = calcular_total_gasto(schema)
            resposta = f"📊 Total gasto no mês: R$ {format(total, ',.2f').replace(',', '.')}"
            await enviar_mensagem_whatsapp(telefone, resposta)
            log_tempos(inicio, timestamp_whatsapp, logger, mensagem, telefone)
            return {"status": "OK", "resposta": resposta}

        elif mensagem_lower == "fatura paga!":
            pagar_fatura(schema)
            resposta = "✅ Todas as compras parceladas deste mês foram adicionadas ao total de gastos!"
            await enviar_mensagem_whatsapp(telefone, resposta)
            log_tempos(inicio, timestamp_whatsapp, logger, mensagem, telefone)
            return {"status": "OK", "resposta": resposta}

        elif mensagem_lower.startswith("salario "):
            resposta = registrar_salario(mensagem, schema)
            await enviar_mensagem_whatsapp(telefone, resposta)
            log_tempos(inicio, timestamp_whatsapp, logger, mensagem, telefone)
            return {"status": "OK", "resposta": resposta}
        
        elif mensagem_lower == "gráficos":
            token_info = gerar_token_acesso(telefone)
            if not token_info:
                resposta = "❌ Erro ao gerar seu link de acesso aos gráficos. Tente novamente mais tarde."
            else:
                token = token_info["token"]
                expira_em = token_info["expira_em"]
                link = f"https://dashboard-financas.up.railway.app/?phone={telefone}&token={token}"
                resposta = (
                    f"📊 *Seu link personalizado para visualizar os gráficos:*\n\n"
                    f"{link}\n\n"
                    f"⚠️ O link é válido por 30 minutos (até as *{expira_em.strftime('%H:%M')}*).\n"
                    f"Depois disso, será necessário gerar um novo link digitando 'gráficos' novamente."
                )

            await enviar_mensagem_whatsapp(telefone, resposta)
            log_tempos(inicio, timestamp_whatsapp, logger, mensagem, telefone)
            return {"status": "OK", "resposta": resposta}

        elif mensagem_lower.startswith("cep "):
            partes = mensagem.split()
            if len(partes) == 2 and partes[1].isdigit():
                cep = partes[1]
                resposta = buscar_cep(cep)
            else:
                resposta = "❌ Formato inválido. Use: `cep 05424020` (apenas números)."

            await enviar_mensagem_whatsapp(telefone, resposta)
            return {"status": "OK", "resposta": resposta}

        elif mensagem_lower == "cotação":
            resposta = obter_cotacao_principais(API_COTACAO, MOEDA_EMOJIS)
            await enviar_mensagem_whatsapp(telefone, resposta)
            log_tempos(inicio, timestamp_whatsapp, logger, mensagem, telefone)
            return {"status": "OK", "resposta": resposta}
        
        elif mensagem_lower.startswith("cotação") and ("-" in mensagem_lower or len(partes) == 2):
            moeda_origem = partes[1].upper()
            resposta = obter_cotacao(API_COTACAO, MOEDAS, CONVERSOES, moeda_origem)
            await enviar_mensagem_whatsapp(telefone, resposta)
            log_tempos(inicio, timestamp_whatsapp, logger, mensagem, telefone)
            return {"status": "OK", "resposta": resposta}
        
        elif mensagem_lower.startswith("cotação") and ("-" in mensagem_lower or len(partes) > 2):
            moeda_origem = partes[1].upper()
            moeda_destino = partes[3].upper()
            resposta = obter_cotacao(API_COTACAO, MOEDAS, CONVERSOES, moeda_origem, moeda_destino)
            await enviar_mensagem_whatsapp(telefone, resposta)
            log_tempos(inicio, timestamp_whatsapp, logger, mensagem, telefone)
            return {"status": "OK", "resposta": resposta}
        
        elif mensagem_lower == "listar moedas":
            resposta = listar_moedas_disponiveis(MOEDAS)
            await enviar_mensagem_whatsapp(telefone, resposta)
            return {"status": "OK", "resposta": resposta}

        elif mensagem_lower == "listar conversoes":
            resposta = listar_conversoes_disponiveis(CONVERSOES)
            await enviar_mensagem_whatsapp(telefone, resposta)
            return {"status": "OK", "resposta": resposta}
        elif mensagem_lower.startswith("conversoes "):
            partes = mensagem.split()
            if len(partes) == 2:
                moeda = partes[1].upper()
                if moeda in CONVERSOES:
                    resposta = listar_conversoes_disponiveis_moeda(CONVERSOES, moeda)
                else:
                    resposta = f"⚠️ Moeda '{moeda}' não encontrada ou não tem conversões disponíveis."
            else:
                resposta = "❌ Formato inválido. Use: conversoes [moeda]"

            await enviar_mensagem_whatsapp(telefone, resposta)
            return {"status": "OK", "resposta": resposta}


        elif mensagem_lower.startswith("lembrete:") and "cron:" in mensagem_lower:
            resposta = processar_lembrete_formatado(mensagem, telefone)
            if resposta:
                await enviar_mensagem_whatsapp(telefone, resposta)
                return {"status": "ok"}

        elif mensagem_lower == "tabela cron":
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
        elif mensagem_lower == "lista lembretes":
            lembretes = listar_lembretes(telefone, schema)
            if not lembretes:
                resposta = "📭 Você ainda não possui lembretes cadastrados."
            else:
                resposta = "📋 *Seus lembretes:*\n\n" + "\n".join(
                    [f"🆔 {l['id']} - \"{l['mensagem']}\"\n⏰ CRON: `{l['cron']}`\n" for l in lembretes]
                )
            await enviar_mensagem_whatsapp(telefone, resposta)
            return {"status": "ok"}
        elif mensagem_lower.startswith("apagar lembrete"):
            partes = mensagem_lower.split()
            if len(partes) >= 3 and partes[2].isdigit():
                id_lembrete = int(partes[2])
                sucesso = apagar_lembrete(telefone, id_lembrete, schema)
                resposta = "🗑️ Lembrete apagado com sucesso!" if sucesso else "⚠️ Lembrete não encontrado ou não pertence a você."
            else:
                resposta = "❌ Formato inválido. Use: apagar lembrete [ID]"
            await enviar_mensagem_whatsapp(telefone, resposta)
            return {"status": "ok"}
        elif mensagem_lower.startswith("liberar "):
            partes = mensagem.split()
            if len(partes) >= 3:
                numero_para_liberar = partes[1]
                nome_usuario = " ".join(partes[2:])
                if telefone == os.getenv("ADMIN_PHONE"):
                    try:
                        liberar_usuario(numero_para_liberar, nome_usuario)
                        resposta = f"✅ Número {numero_para_liberar} ({nome_usuario}) autorizado com sucesso!"

                        # ✅ Envia mensagem para o novo usuário liberado
                        texto_bem_vindo = (
                            f"🎉 Olá usuário!\n"
                            f"Seu número foi autorizado e agora você pode usar o assistente financeiro via WhatsApp. "
                            f"Digite 'ajuda' para ver os comandos disponíveis."
                        )
                        await enviar_mensagem_whatsapp(numero_para_liberar, texto_bem_vindo)

                    except Exception as e:
                        logger.error("❌ Erro ao liberar usuário: %s", str(e))
                        resposta = f"❌ Erro ao autorizar o número: {e}"
                else:
                    resposta = "⚠️ Apenas o administrador pode liberar novos usuários."
            else:
                resposta = "❌ Formato inválido. Use: liberar [número] [nome]"

            await enviar_mensagem_whatsapp(telefone, resposta)
            return {"status": "OK", "resposta": resposta}
        elif mensagem_lower.startswith("não liberar "):
            partes = mensagem.split()
            if len(partes) >= 2:
                numero_negado = partes[2] if len(partes) >= 3 else partes[1]
                if telefone == os.getenv("ADMIN_PHONE"):
                    # Mensagem para o admin (confirmação)
                    resposta = f"🚫 Número {numero_negado} não foi autorizado."

                    # Mensagem para o usuário negado
                    texto_usuario = (
                        "🚫 Seu número **não foi autorizado** a usar o assistente financeiro no momento. "
                        "Em caso de dúvidas, entre em contato com o administrador."
                    )
                    await enviar_mensagem_whatsapp(numero_negado, texto_usuario)
                else:
                    resposta = "⚠️ Apenas o administrador pode negar autorizações."
            else:
                resposta = "❌ Formato inválido. Use: não liberar [número]"

            await enviar_mensagem_whatsapp(telefone, resposta)
            return {"status": "OK", "resposta": resposta}
        elif mensagem_lower == "lista usuarios":
            if telefone != os.getenv("ADMIN_PHONE"):
                await enviar_mensagem_whatsapp(telefone, "⚠️ Apenas o administrador pode acessar essa lista.")
                return {"status": "acesso negado"}

            usuarios = listar_usuarios_autorizados()
            if not usuarios:
                resposta = "📭 Nenhum número autorizado encontrado."
            else:
                resposta = "✅ *Usuários autorizados:*\n\n" + "\n".join(
                    [f"👤 {nome or '(sem nome)'} - {tel}" for nome, tel, _ in usuarios]
                )

            await enviar_mensagem_whatsapp(telefone, resposta)
            return {"status": "OK", "resposta": "lista enviada"}
        
        elif mensagem_lower.startswith("revogar "):
            numero_para_revogar = mensagem.split(" ")[1]
            if telefone == os.getenv("ADMIN_PHONE"):
                sucesso = revogar_autorizacao(numero_para_revogar)
                if sucesso:
                    resposta = f"🚫 Número {numero_para_revogar} teve a autorização revogada com sucesso!"
                else:
                    resposta = "⚠️ Número não encontrado ou já está desautorizado."
            else:
                resposta = "⚠️ Apenas o administrador pode revogar autorizações."

            await enviar_mensagem_whatsapp(telefone, resposta)
            return {"status": "OK", "resposta": resposta}

        elif (
            any(char.isdigit() for char in mensagem)
            and " " in mensagem
            and "cep" not in mensagem_lower
            and not (len(mensagem.split()) >= 2 and mensagem.split()[1].startswith("55"))
        ):
            descricao, valor, categoria, meio_pagamento, parcelas = processar_mensagem(mensagem)

            logger.info(
                "✅ Gasto reconhecido: %s | Valor: %.2f | Categoria: %s | Meio de Pagamento: %s | Parcelas: %d",
                descricao, valor, categoria, meio_pagamento, parcelas
            )

            if meio_pagamento in ["pix", "débito"]:
                salvar_gasto(descricao, valor, categoria, meio_pagamento, schema, parcelas)
                resposta = f"✅ Gasto de R$ {format(valor, ',.2f').replace(',', '.')} em '{categoria}' registrado com sucesso!"
            else:
                salvar_fatura(descricao, valor, categoria, meio_pagamento, parcelas, schema)
                resposta = f"✅ Compra parcelada registrada! {parcelas}x de R$ {valor/parcelas:.2f}"

            await enviar_mensagem_whatsapp(telefone, resposta)
            log_tempos(inicio, timestamp_whatsapp, logger, mensagem, telefone)
            return {"status": "OK", "resposta": resposta}
        else:
            resposta = (
                "⚠️ Comando não reconhecido.\n"
                "Digite *ajuda* para ver a lista de comandos disponíveis."
            )
            await enviar_mensagem_whatsapp(telefone, resposta)
            return {"status": "comando inválido", "resposta": resposta}

    except Exception as e:
        logger.exception("❌ Erro ao processar webhook:")
        return JSONResponse(content={"status": "erro", "mensagem": str(e)}, status_code=500)

def obter_schema_por_telefone(telefone):
    """
    Consulta a tabela 'usuarios' e retorna o nome do schema com base no telefone.
    """
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute("SELECT nome FROM usuarios WHERE telefone = %s AND autorizado = true", (telefone,))
    resultado = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if resultado:
        nome = resultado[0]
        schema = nome.strip().lower().replace(" ", "_")
        return schema
    else:
        return None

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

COMANDOS = [
    {
        "comando": "ajuda",
        "descricao": "Mostra este menu",
        "admin_only": False,
    },
    {
        "comando": "total gasto",
        "descricao": "Exibe o total de gastos do mês",
        "admin_only": False,
    },
    {
        "comando": "gráficos",
        "descricao": "Envia um link com os gráficos financeiros",
        "admin_only": False,
    },
    {
        "comando": "fatura paga!",
        "descricao": "Informa que sua fatura foi paga",
        "admin_only": False,
    },
    {
        "comando": "cotação",
        "descricao": "Mostra as principais moedas do dia",
        "admin_only": False,
    },
    {
        "comando": "lista cotação",
        "descricao": "Lista todas as moedas disponíveis",
        "admin_only": False,
    },
    {
        "comando": "cotação [moeda]",
        "descricao": "Mostra a cotação da moeda (ex: cotação USD)",
        "admin_only": False,
    },
    {
        "comando": "cotação [moeda1]-[moeda2]",
        "descricao": "Conversão entre duas moedas (ex: cotação USD-EUR)",
        "admin_only": False,
    },
    {
        "comando": "cep [número]",
        "descricao": "Retorna o endereço correspondente ao CEP",
        "admin_only": False,
    },
    {
        "comando": "lembrete: \"msg\" + cron: padrão",
        "descricao": "Agenda um lembrete com cron",
        "admin_only": False,
    },
    {
        "comando": "tabela cron",
        "descricao": "Exibe exemplos de agendamento CRON",
        "admin_only": False,
    },
    {
        "comando": "lista lembretes",
        "descricao": "Lista todos os lembretes ativos",
        "admin_only": False,
    },
    {
        "comando": "apagar lembrete [id]",
        "descricao": "Apaga um lembrete específico",
        "admin_only": False,
    },
    # 👑 Admin
    {
        "comando": "liberar [telefone] [nome]",
        "descricao": "Autoriza novo número e cria schema",
        "admin_only": True,
    },
    {
        "comando": "não liberar [telefone]",
        "descricao": "Recusa um número e envia notificação ao usuário",
        "admin_only": True,
    },
    {
        "comando": "lista usuarios",
        "descricao": "Lista todos os usuários autorizados",
        "admin_only": True,
    },
    {
        "comando": "revogar [telefone]",
        "descricao": "Revoga a autorização de um número",
        "admin_only": True,
    },
]

async def exibir_menu_ajuda(telefone: str):
    admin_phone = os.getenv("ADMIN_PHONE")
    is_admin = telefone == admin_phone

    titulo = "🛠️ *Menu de Ajuda - Administrador*" if is_admin else "🤖 *Menu de Ajuda - Assistente Financeiro*"
    texto_ajuda = [titulo, "\n📌 *Comandos disponíveis:*"]

    for cmd in COMANDOS:
        if not cmd["admin_only"] or is_admin:
            texto_ajuda.append(f"• `{cmd['comando']}` → {cmd['descricao']}")

    if not is_admin:
        texto_ajuda.append("\n🧠 *Exemplo de lembrete:*\n"
                           "`lembrete: \"Pagar conta\"`\n"
                           "`cron: 0 9 * * 1-5` → Todos os dias úteis às 9h")

    await enviar_mensagem_whatsapp(telefone, "\n".join(texto_ajuda))
