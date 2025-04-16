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
import fasttext

from backend.utils import (
    mensagem_ja_processada, registrar_mensagem_recebida, obter_schema_por_telefone
)
from backend.services.scheduler import scheduler, agendar_lembrete_cron
from backend.services.whatsapp_service import enviar_mensagem_whatsapp, obter_url_midia, baixar_midia
from backend.services.db_init import inicializar_bd
from backend.services.api_service import (
    obter_cotacao_principais, obter_cotacao, buscar_cep, listar_moedas_disponiveis, listar_conversoes_disponiveis, listar_conversoes_disponiveis_moeda, MOEDAS, CONVERSOES, MOEDA_EMOJIS
)
from backend.services.gastos_service import (
    salvar_gasto, salvar_fatura, calcular_total_gasto, pagar_fatura, registrar_salario, listar_lembretes, apagar_lembrete
)
from backend.services.autorizacao_service import verificar_autorizacao, liberar_usuario
from backend.services.usuarios_service import listar_usuarios_autorizados, revogar_autorizacao
from backend.services.token_service import gerar_token_acesso
from backend.services.noticias_service import obter_boletim_the_news
from backend.services.leitura_service import (
    try_all_techniques, processar_qrcode_com_ocr, processar_codigodebarras_com_pdfplumber, gerar_descricao_para_classificacao
)
from backend.services.email_service import (
    buscar_credenciais_email,
    salvar_credenciais_email,
    formatar_emails_para_whatsapp,
    get_emails_info
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

caminho_modelo = os.path.join("backend", "models", "modelo_gastos_prod.bin")
MODELO_FASTTEXT = fasttext.load_model(caminho_modelo)

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
        telefone = mensagem_obj["from"]
        mensagem_id = mensagem_obj["id"]
        timestamp_whatsapp = int(mensagem_obj["timestamp"])

        # Proteção e roteamento por tipo de mídia
        tipo_msg = mensagem_obj.get("type")

        if mensagem_ja_processada(mensagem_id):
            logger.warning("⚠️ Mensagem já processada anteriormente: %s", mensagem_id)
            return JSONResponse(content={
                "status": "ignorado",
                "mensagem": "Mensagem duplicada ignorada."
            }, status_code=200)

        # Registra a mensagem recebida no banco
        registrar_mensagem_recebida(mensagem_id, telefone, tipo_msg)

        if tipo_msg == "text":
            mensagem = mensagem_obj["text"]["body"].strip()
            mensagem_lower = mensagem.lower()

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
                token = token_info["token"]
                expira_em = token_info["expira_em"]

                print("👀 DEBUG Telefone:", telefone)
                print("👀 DEBUG Token:", token)

                resposta = (
                    "📊 Aqui está o seu link com os gráficos financeiros!\n\n"
                    f"🔗 https://dashboard-financas.up.railway.app/?phone={telefone}&token={token}\n"
                    f"⚠️ O link é válido até às {expira_em.strftime('%H:%M')} por segurança."
                )

                print("🔗 Link final gerado:", resposta)
                
                await enviar_mensagem_whatsapp(telefone, resposta)
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
            
            elif mensagem_lower.startswith("cotação") and len(partes) == 2:
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
                            liberar_usuario(nome_usuario, numero_para_liberar)
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
            
            elif mensagem_lower in ["notícias", "boletim", "the news"]:
                await enviar_mensagem_whatsapp(telefone, "📰 Um instante... buscando o boletim mais recente.")
                mensagens = obter_boletim_the_news()
                if not mensagens:
                    await enviar_mensagem_whatsapp(telefone, "❌ Não foi possível carregar o boletim de hoje.")
                    return {"status": "Erro", "resposta": "Falha ao capturar o boletim."}
                for bloco in mensagens:
                    await enviar_mensagem_whatsapp(telefone, bloco)
                return {"status": "OK", "resposta": "Boletim enviado com sucesso"}

            elif "resumo dos emails" in mensagem.lower():
                email_user, email_pass = buscar_credenciais_email(telefone)
                if not email_user or not email_pass:
                    resposta = (
                        "📩 Para acessar seus e-mails, preciso das credenciais do Gmail.\n\n"
                        "Por favor, envie no seguinte formato:\n\n"
                        "email: seu_email@gmail.com\n"
                        "senha: sua_senha_de_app"
                    )
                else:
                    emails = get_emails_info(email_user, email_pass)
                    resposta = formatar_emails_para_whatsapp(emails)

                await enviar_mensagem_whatsapp(telefone, resposta)

            elif mensagem.lower().startswith("email:"):
                linhas = mensagem.strip().splitlines()
                if len(linhas) >= 2 and "senha:" in linhas[1].lower():
                    email_user = linhas[0].split(":", 1)[1].strip()
                    email_pass = linhas[1].split(":", 1)[1].strip()

                    salvar_credenciais_email(telefone, email_user, email_pass)
                    await enviar_mensagem_whatsapp(
                        telefone,
                        "✅ Credenciais de e-mail salvas com sucesso! Agora é só mandar 'resumo dos emails'."
                    )
                else:
                    await enviar_mensagem_whatsapp(
                        telefone,
                        "❌ Formato inválido. Envie assim:\nemail: seu_email@gmail.com\nsenha: sua_senha_de_app"
                    )
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
        
        elif mensagem_obj["type"] == "image" or mensagem_obj["type"] == "document":
            media_id = mensagem_obj[mensagem_obj["type"]]["id"]
            telefone = mensagem_obj["from"]
            logger.info(f"📎 Mídia recebida ({mensagem_obj['type']}) com media_id={media_id}")

            url_midia = await obter_url_midia(media_id)
            if not url_midia:
                await enviar_mensagem_whatsapp(telefone, f"❌ Não consegui acessar a {mensagem_obj['type']}. Tente novamente.")
                return {"status": "erro", "mensagem": f"Não foi possível obter a URL da {mensagem_obj['type']}"}

            extensao = ".jpeg" if mensagem_obj["type"] == "image" else ".pdf"
            caminho_arquivo = f"temp_{media_id}{extensao}"
            await baixar_midia(url_midia, caminho_arquivo)

            if mensagem_obj["type"] == "image":
                resultado = try_all_techniques(caminho_arquivo, media_id)
                if not resultado:
                    await enviar_mensagem_whatsapp(telefone, "⚠️ Não consegui extrair nenhuma informação da imagem.")
                    return {"status": "erro", "mensagem": "Decodificação falhou"}

                tipo = resultado.get("tipo", "Desconhecido").upper()
                consulta_url = resultado.get("consulta_url")
                chave = resultado.get("chave")

                if tipo == "QRCODE":
                    msg = (
                        f"🔍 QR Code identificado!\nURL de consulta: {consulta_url}\n\n"
                        "✅ Para continuar:\n1. Acesse o link acima\n2. Clique em *Continuar consulta de NFC-e*\n3. Clique em *Imprimir Danfe* e envie o PDF aqui."
                    )
                elif tipo in ["PDF417", "CODE128"]:
                    msg = (
                        f"📦 Código de barras detectado!\nChave de Acesso: {chave}\n\n"
                        "✅ Para consultar:\n1. Acesse: https://www.nfe.fazenda.gov.br/portal/consultaRecaptcha.aspx?tipoConsulta=resumo&tipoConteudo=7PhJ+gAVw2g=\n"
                        "2. Cole a Chave de Acesso\n3. Clique em *Consultar*\n4. Clique em *Preparar documento para impressão* e depois no símbolo de impressora\n"
                        "5. Salve e envie o PDF aqui."
                    )
                else:
                    msg = "❌ Tipo de código não reconhecido. Por favor envie uma imagem com QR Code ou código de barras."

                await enviar_mensagem_whatsapp(telefone, msg)
                return {"status": "OK", "mensagem": "Imagem processada"}

            elif mensagem_obj["type"] == "document":
                nome_arquivo = mensagem_obj["document"].get("filename", f"documento_{media_id}.pdf")

                if "Portal da Nota Fiscal Eletrônica" in nome_arquivo.lower():
                    dados = processar_codigodebarras_com_pdfplumber(caminho_arquivo)
                else:
                    dados = processar_qrcode_com_ocr(caminho_arquivo)

                descricao = gerar_descricao_para_classificacao(dados)
                await enviar_mensagem_whatsapp(telefone, f"📋 {descricao}\n✅ Gasto registrado com sucesso!")
                return {"status": "OK", "mensagem": "PDF processado"}

        else:
            logger.warning(f"❌ Tipo de mensagem não suportado: {tipo_msg}")
            await enviar_mensagem_whatsapp(
                telefone,
                "⚠️ Tipo de mensagem não reconhecido. Envie texto, imagem com QR Code ou PDF com DANFE."
            )
            return {"status": "ignorado", "mensagem": "Tipo de mídia não suportado"}
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
            parte_limpa = parte.replace(".", "").replace(",", "")
            if parte_limpa.isdigit():
                valor = float(parte.replace(",", "."))
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

        categoria, probabilidade = definir_categoria(descricao)
        logger.info(f"📊 Categoria prevista: {categoria} ({probabilidade:.2%})")
        return descricao.strip(), valor, categoria, meio_pagamento, parcelas

    except Exception as e:
        logger.exception("❌ Erro ao processar mensagem:")
        return "Erro", 0.0, "Desconhecido", "Desconhecido", 1

def definir_categoria(descricao: str):
    """
    Usa o modelo FastText para prever a categoria a partir da descrição.
    """
    predicao = MODELO_FASTTEXT.predict(descricao)
    categoria_predita = predicao[0][0].replace("__label__", "")
    probabilidade = predicao[1][0]

    return categoria_predita, probabilidade

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
    {
        "comando": "notícias",
        "descricao": "Envia o boletim mais recente do The News",
        "admin_only": False,
    },
    {
        "comando": "resumo dos emails",
        "descricao": "Busca os e-mails recentes do seu Gmail",
        "admin_only": False,
    },
    {
        "comando": "email: seu_email + senha: sua_senha",
        "descricao": "Salva suas credenciais de e-mail para acesso",
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
