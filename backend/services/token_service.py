from datetime import datetime, timedelta
import secrets
from .db_init import conectar_bd
import pytz  # <- você pode adicionar ao requirements.txt

def gerar_token_acesso(telefone: str) -> dict:
    fuso_brasilia = pytz.timezone("America/Sao_Paulo")
    agora = datetime.now(fuso_brasilia)
    expira_em = agora + timedelta(minutes=30)
    token = secrets.token_urlsafe(16)

    conn = conectar_bd()
    cursor = conn.cursor()

    # 🔍 Buscar schema
    cursor.execute("SELECT schema_user FROM usuarios WHERE telefone = %s", (telefone,))
    resultado = cursor.fetchone()

    if not resultado or not resultado[0]:
        cursor.close()
        conn.close()
        raise ValueError("❌ Schema do usuário não encontrado.")

    schema = resultado[0]

    # 🧹 Limpar tokens expirados
    cursor.execute("DELETE FROM tokens_ativos WHERE expira_em < NOW()")

    # 🆕 Inserir token
    cursor.execute("""
        INSERT INTO tokens_ativos (telefone, token, schema, criado_em, expira_em)
        VALUES (%s, %s, %s, %s, %s)
    """, (telefone, token, schema, agora, expira_em))

    conn.commit()
    cursor.close()
    conn.close()

    return {
        "token": token,
        "expira_em": expira_em,
        "schema": schema
    }

def validar_token(telefone: str, token: str) -> tuple[str, datetime] | None:
    conn = conectar_bd()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT schema, expira_em FROM tokens_ativos
        WHERE telefone = %s AND token = %s AND expira_em > NOW()
        """,
        (telefone, token)
    )
    resultado = cursor.fetchone()
    cursor.close()
    conn.close()

    if resultado:
        return resultado[0], resultado[1]  # schema, expira_em
    return None