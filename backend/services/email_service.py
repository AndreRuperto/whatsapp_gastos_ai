import logging
import psycopg2
import os
from dotenv import load_dotenv
from email.utils import parsedate_to_datetime
from email.header import decode_header
from datetime import datetime, timedelta
import imaplib, email, pytz, re

load_dotenv()
logger = logging.getLogger(__name__)
DATABASE_URL = os.getenv("DATABASE_URL")

def salvar_credenciais_email(telefone, email_user, email_pass, descricao=None):
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    schema = obter_schema_por_telefone(telefone)

    # Verificar se o email já existe
    cur.execute(
        f"""SELECT id FROM {schema}.email 
            WHERE telefone = %s AND email_user = %s""",
        (telefone, email_user)
    )
    email_existente = cur.fetchone()
    
    descricao = descricao or email_user  # Se não fornecer descrição, usa o próprio email
    
    if email_existente:
        # Se o email já existe, atualiza os dados
        cur.execute(
            f"""UPDATE {schema}.email 
                SET email_pass = %s, descricao = %s, data_inclusao = NOW()
                WHERE id = %s""",
            (email_pass, descricao, email_existente[0])
        )
        logger.info(f"Credenciais atualizadas para o email {email_user}")
    else:
        # Se o email não existe, insere novo registro
        cur.execute(
            f"""INSERT INTO {schema}.email (telefone, email_user, email_pass, descricao, data_inclusao)
                VALUES (%s, %s, %s, %s, NOW());""",
            (telefone, email_user, email_pass, descricao)
        )
        logger.info(f"Novas credenciais salvas para o email {email_user}")

    conn.commit()
    cur.close()
    conn.close()

def listar_emails_cadastrados(telefone):
    """Lista todos os emails cadastrados para o telefone específico"""
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    schema = obter_schema_por_telefone(telefone)

    cur.execute(
        f"""SELECT email_user, descricao
            FROM {schema}.email
            WHERE telefone = %s
            ORDER BY data_inclusao DESC;""",
        (telefone,)
    )

    resultados = cur.fetchall()
    cur.close()
    conn.close()

    return resultados

def buscar_credenciais_email(telefone, email_especifico=None):
    """
    Busca credenciais de email do usuário
    Se email_especifico for fornecido, busca apenas esse email
    Caso contrário, retorna o email mais recente
    """
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    schema = obter_schema_por_telefone(telefone)

    if email_especifico:
        # Busca pelo email específico
        cur.execute(
            f"""SELECT email_user, email_pass
                FROM {schema}.email
                WHERE telefone = %s AND email_user = %s
                ORDER BY data_inclusao DESC LIMIT 1;""",
            (telefone, email_especifico)
        )
    else:
        # Busca o email mais recente
        cur.execute(
            f"""SELECT email_user, email_pass
                FROM {schema}.email
                WHERE telefone = %s
                ORDER BY data_inclusao DESC LIMIT 1;""",
            (telefone,)
        )

    resultado = cur.fetchone()
    cur.close()
    conn.close()

    if resultado:
        return resultado[0], resultado[1]
    return None, None

def obter_schema_por_telefone(telefone):
    """
    Consulta a tabela 'usuarios' e retorna o nome do schema com base no telefone.
    """
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute("SELECT schema_user FROM usuarios WHERE telefone = %s AND autorizado = true", (telefone,))
    resultado = cursor.fetchone()
    nome = resultado[0]
    cursor.close()
    conn.close()
    
    return nome

def decode_header_value(value):
    """
    Decodifica cabeçalhos de email que podem conter diferentes codificações
    """
    if not value:
        return ""
    
    try:
        decoded_parts = decode_header(value)
        return ''.join(part.decode(enc or 'utf-8') if isinstance(part, bytes) else part for part, enc in decoded_parts)
    except Exception as e:
        logger.error(f"Erro ao decodificar cabeçalho: {e}")
        return value

def categorize_email(email_from, subject):
    if re.search(r'promo(ção|tions)', subject, re.IGNORECASE) or re.search(r'promo(ção|tions)', email_from, re.IGNORECASE):
        return "Promoções"
    elif re.search(r'social', email_from, re.IGNORECASE) or "LinkedIn" in email_from:
        return "Social"
    elif re.search(r'atualiza(ções|tions)', subject, re.IGNORECASE):
        return "Atualizações"
    return "Principal"

def formatar_data_para_imap(data_obj):
    """
    Formata um objeto datetime para o formato IMAP apropriado
    Ex: 16-Apr-2025
    """
    return data_obj.strftime("%d-%b-%Y")

def get_emails_info(email_user, email_pass, data_consulta=None):
    """
    Busca emails no Gmail para uma data específica ou para hoje
    
    Parâmetros:
    - email_user: email do usuário
    - email_pass: senha de aplicativo
    - data_consulta: Data específica no formato "DD-MM-YYYY" (opcional, default: hoje)
    """
    try:
        mail = imaplib.IMAP4_SSL('imap.gmail.com')
        mail.login(email_user, email_pass)
        mail.select("inbox")

        # Define a data de consulta
        if data_consulta:
            try:
                # Debug
                logger.info(f"Consultando emails para data: {data_consulta}")
                
                # Converte a data informada para o formato aceito pelo IMAP
                data_obj = datetime.strptime(data_consulta, "%d-%m-%Y")
                
                # Formato IMAP: DD-MMM-YYYY (Ex: 16-Apr-2025)
                search_date = formatar_data_para_imap(data_obj)
                
                # Usar formato SINCE e BEFORE para pegar um único dia
                next_day = data_obj + timedelta(days=1)
                next_day_str = formatar_data_para_imap(next_day)
                
                # Criar critério de busca: emails do dia específico
                search_criteria = f'(SINCE "{search_date}" BEFORE "{next_day_str}")'
                
                # Debug
                logger.info(f"Critério de busca IMAP: {search_criteria}")
                
            except ValueError as e:
                # Se a data for inválida, usa a data atual
                logger.error(f"Data inválida: {data_consulta}. Erro: {e}")
                today = datetime.now()
                search_date = formatar_data_para_imap(today)
                search_criteria = f'(SINCE "{search_date}")'
        else:
            # Se não informou data, busca emails de hoje
            today = datetime.now()
            search_date = formatar_data_para_imap(today)
            tomorrow = today + timedelta(days=1)
            tomorrow_str = formatar_data_para_imap(tomorrow)
            search_criteria = f'(SINCE "{search_date}" BEFORE "{tomorrow_str}")'
            logger.info(f"Buscando emails de hoje ({search_date})")

        # Executa a busca
        logger.info(f"Executando busca IMAP: {search_criteria}")
        status, data = mail.search(None, search_criteria)
        
        # Debug
        logger.info(f"Status da busca: {status}")
        logger.info(f"IDs de emails encontrados: {data}")
        
        mail_ids = data[0].split() if data[0] else []
        local_tz = pytz.timezone('America/Sao_Paulo')

        emails_info = []
        for num in mail_ids:
            status, data = mail.fetch(num, '(RFC822)')
            for response_part in data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    email_from = decode_header_value(msg['From'])
                    subject = decode_header_value(msg['Subject'])
                    
                    try:
                        parsed_date = parsedate_to_datetime(msg['Date']).astimezone(local_tz)
                        hora = parsed_date.strftime('%H:%M')
                    except:
                        hora = "hora desconhecida"
                    
                    emails_info.append({
                        'from': email_from,
                        'subject': subject,
                        'time': hora,
                        'section': categorize_email(email_from, subject)
                    })
        mail.logout()
        return emails_info
    except Exception as e:
        logger.exception(f"Erro ao buscar e-mails: {e}")
        return []

def formatar_emails_para_whatsapp(emails_info: list, email_user: str = None, data_consulta: str = None) -> str:
    """
    Formata os emails para envio via WhatsApp
    """
    data_formatada = "hoje"
    if data_consulta:
        try:
            data_obj = datetime.strptime(data_consulta, "%d-%m-%Y")
            data_formatada = data_obj.strftime("%d/%m/%Y")
        except ValueError:
            # Se a data for inválida, mantém "hoje"
            pass
    
    if not emails_info:
        return f"Nenhum e-mail encontrado para {data_formatada}{' em ' + email_user if email_user else ''}."

    header = f"📩 E-mails de {data_formatada}"
    if email_user:
        header += f" em {email_user}"
    header += ":\n\n"
    
    footer = "\n📬 Verifique o Gmail para ler o conteúdo completo."
    mensagem = header
    for i, info in enumerate(reversed(emails_info), 1):
        mensagem += (
            f"{i}. De: {info['from']}\n"
            f"   Assunto: {info['subject']}\n"
            f"   Horário: {info['time']}\n"
            f"   Seção: {info['section']}\n\n"
        )
    mensagem += footer
    return mensagem