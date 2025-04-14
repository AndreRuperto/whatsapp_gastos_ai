from backend.services.db_init import conectar_bd
from backend.utils import obter_schema_por_telefone
from email.utils import parsedate_to_datetime
from email.header import decode_header
from datetime import datetime
import imaplib, email, pytz, re

def salvar_credenciais_email(telefone, email_user, email_pass):
    conn = conectar_bd()
    cur = conn.cursor()
    schema = obter_schema_por_telefone(telefone)

    # Remove credenciais anteriores do mesmo número
    cur.execute(f"DELETE FROM {schema}.email WHERE telefone = %s", (telefone,))
    
    # Insere nova credencial vinculada ao número
    cur.execute(
        f"""INSERT INTO {schema}.email (telefone, email_user, email_pass, data_inclusao)
            VALUES (%s, %s, %s, NOW());""",
        (telefone, email_user, email_pass)
    )

    conn.commit()
    cur.close()
    conn.close()

def buscar_credenciais_email(telefone):
    conn = conectar_bd()
    cur = conn.cursor()
    schema = obter_schema_por_telefone(telefone)

    cur.execute(
        f"""SELECT email_user, email_pass
            FROM {schema}.email
            WHERE telefone = %s
            ORDER BY id DESC LIMIT 1;""",
        (telefone,)
    )

    resultado = cur.fetchone()
    cur.close()
    conn.close()

    if resultado:
        return resultado[0], resultado[1]
    return None, None

def decode_header_value(value):
    decoded_parts = decode_header(value)
    return ''.join(part.decode(enc or 'utf-8') if isinstance(part, bytes) else part for part, enc in decoded_parts)

def categorize_email(email_from, subject):
    if re.search(r'promo(ção|tions)', subject, re.IGNORECASE) or re.search(r'promo(ção|tions)', email_from, re.IGNORECASE):
        return "Promoções"
    elif re.search(r'social', email_from, re.IGNORECASE) or "LinkedIn" in email_from:
        return "Social"
    elif re.search(r'atualiza(ções|tions)', subject, re.IGNORECASE):
        return "Atualizações"
    return "Principal"

def get_emails_info(email_user, email_pass):
    try:
        mail = imaplib.IMAP4_SSL('imap.gmail.com')
        mail.login(email_user, email_pass)
        mail.select("inbox")

        today = datetime.now().strftime("%d-%b-%Y")
        status, data = mail.search(None, f'SINCE {today}')
        mail_ids = data[0].split()
        local_tz = pytz.timezone('America/Sao_Paulo')

        emails_info = []
        for num in mail_ids:
            status, data = mail.fetch(num, '(RFC822)')
            for response_part in data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    email_from = decode_header_value(msg['From'])
                    subject = decode_header_value(msg['Subject'])
                    parsed_date = parsedate_to_datetime(msg['Date']).astimezone(local_tz)
                    emails_info.append({
                        'from': email_from,
                        'subject': subject,
                        'time': parsed_date.strftime('%H:%M'),
                        'section': categorize_email(email_from, subject)
                    })
        mail.logout()
        return emails_info
    except Exception as e:
        print(f"Erro ao buscar e-mails: {e}")
        return []

def formatar_emails_para_whatsapp(emails_info: list) -> str:
    if not emails_info:
        return "Nenhum e-mail novo encontrado hoje."

    header = "📩 Você recebeu novos e-mails:\n\n"
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
    
