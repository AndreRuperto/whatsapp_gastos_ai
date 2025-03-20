import psycopg2
import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
import os
from backend import enviar_mensagem_whatsapp

# Carregar variáveis do .env
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
SEU_NUMERO_WHATSAPP = os.getenv("WHATSAPP_NUMBER")

def alerta_fatura():
    """
    Envia um alerta no início do mês com o valor da fatura do cartão.
    """
    hoje = datetime.date.today()
    primeiro_dia_mes = hoje.replace(day=1)

    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute("SELECT SUM(valor) FROM fatura_cartao WHERE data_fim BETWEEN %s AND %s",
                   (primeiro_dia_mes, primeiro_dia_mes + datetime.timedelta(days=30)))
    total_fatura = cursor.fetchone()[0] or 0.0
    cursor.close()
    conn.close()

    if total_fatura > 0:
        mensagem = f"💳 Sua fatura do cartão deste mês é R$ {total_fatura:.2f}. Não esqueça de pagar! 📆"
        enviar_mensagem_whatsapp(SEU_NUMERO_WHATSAPP, mensagem)

# Criar agendador para rodar no primeiro dia do mês às 9h
scheduler = BackgroundScheduler()
scheduler.add_job(alerta_fatura, "cron", day=1, hour=9)
scheduler.start()