import secrets
from datetime import datetime, timedelta
from .db_init import conectar_bd

def gerar_token_acesso(phone: str, schema: str) -> tuple[str, datetime]:
    token = secrets.token_urlsafe(16)
    expira_em = datetime.now() + timedelta(minutes=30)

    conn = conectar_bd()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM tokens_ativos WHERE expira_em < NOW()")

    cursor.execute(
        """
        INSERT INTO tokens_ativos (phone, token, schema, criado_em, expira_em)
        VALUES (%s, %s, %s, NOW(), %s)
        """,
        (phone, token, schema, expira_em)
    )
    conn.commit()
    cursor.close()
    conn.close()

    return token, expira_em

def validar_token(phone: str, token: str) -> str | None:
    conn = conectar_bd()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT schema FROM tokens_ativos
        WHERE phone = %s AND token = %s AND expira_em > NOW()
        """,
        (phone, token)
    )
    resultado = cursor.fetchone()
    cursor.close()
    conn.close()

    return resultado[0] if resultado else None