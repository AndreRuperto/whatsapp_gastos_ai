# scheduler.py
import psycopg2
import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv
import os
from backend.services.whatsapp_service import enviar_mensagem_whatsapp

# Carregar variáveis do .env
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

scheduler = BackgroundScheduler()
scheduler.start()

def alerta_fatura():
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
        enviar_mensagem_whatsapp(os.getenv("WHATSAPP_NUMBER"), mensagem)

scheduler.add_job(alerta_fatura, "cron", day=1, hour=9)

def normalizar_cron(expr):
    partes = expr.strip().split()
    while len(partes) < 5:
        partes.append("*")
    if len(partes) != 5:
        raise ValueError("Expressão cron inválida. Deve ter até 5 partes.")
    return partes

def agendar_lembrete_cron(telefone: str, mensagem: str, cron_expr: str):
    try:
        cron_parts = normalizar_cron(cron_expr)
        trigger = CronTrigger(
            minute=cron_parts[0],
            hour=cron_parts[1],
            day=cron_parts[2],
            month=cron_parts[3],
            day_of_week=cron_parts[4]
        )

        job_id = f"lembrete_{telefone}_{'_'.join(cron_parts)}_{hash(mensagem)}"

        scheduler.add_job(
            enviar_mensagem_whatsapp,
            trigger=trigger,
            args=[telefone, mensagem],
            id=job_id,
            replace_existing=True
        )

        print(f"✅ Lembrete agendado para {telefone}: '{mensagem}' → {cron_expr}")

        # Salvar no banco
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO lembretes (telefone, mensagem, cron)
            VALUES (%s, %s, %s)
        """, (telefone, mensagem, cron_expr))
        conn.commit()
        cursor.close()
        conn.close()

    except Exception as e:
        print(f"Erro ao agendar lembrete: {e}")

def carregar_lembretes_salvos():
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute("SELECT telefone, mensagem, cron FROM lembretes")
    lembretes = cursor.fetchall()
    cursor.close()
    conn.close()

    for telefone, mensagem, cron in lembretes:
        agendar_lembrete_cron(telefone, mensagem, cron)

carregar_lembretes_salvos()