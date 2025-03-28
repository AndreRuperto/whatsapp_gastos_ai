import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
import streamlit as st
import pandas as pd
import psycopg2
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
import pytz
from services.token_service import validar_token

load_dotenv()

st.set_page_config(page_title="Dashboard Financeiro", layout="wide")
st.title("📊 Dashboard de Gastos - WhatsApp AI")
st.markdown("---")

# ✅ Método compatível e funcional para Streamlit 1.32.0
query_params = st.experimental_get_query_params()
phone = query_params.get("phone", [None])[0]
token = query_params.get("token", [None])[0]

print("📲 Telefone:", phone)
print("🔐 Token:", token)

resultado = validar_token(phone, token)
if not resultado:
    st.error("🔒 Link inválido ou expirado. Solicite um novo link.")
    st.stop()

schema, expira_em = resultado

# 🎯 Alerta de expiração com fuso de Brasília
fuso_brasilia = pytz.timezone("America/Sao_Paulo")
agora = datetime.now(fuso_brasilia)
expira_em = expira_em.astimezone(fuso_brasilia)  # ✅ exibição no fuso correto

minutos_restantes = int((expira_em - agora).total_seconds() // 60)
expira_formatado = expira_em.strftime("%H:%M")

if minutos_restantes <= 0:
    st.error("❌ Este link já expirou. Por favor, solicite um novo.")
    st.stop()
elif minutos_restantes <= 5:
    st.warning(f"⚠️ Seu link expira em {minutos_restantes} minutos (às {expira_formatado}). Salve os dados se necessário.")
else:
    st.info(f"🔐 Link válido até às {expira_formatado} (horário de Brasília).")

DATABASE_URL = os.getenv("DATABASE_URL")
conn = psycopg2.connect(DATABASE_URL)
query = f"SELECT descricao, valor, categoria, meio_pagamento, data FROM {schema}.gastos ORDER BY data DESC"
df = pd.read_sql(query, conn)

st.subheader("💰 Últimos Gastos Registrados")
st.dataframe(df)

categoria = st.selectbox("Filtrar por Categoria", ["Todas"] + list(df["categoria"].unique()))
if categoria != "Todas":
    df = df[df["categoria"] == categoria]

st.subheader("📅 Gastos ao longo do tempo")
df["data"] = pd.to_datetime(df["data"])
df = df.copy()
df.set_index("data", inplace=True)
st.line_chart(df["valor"])

st.subheader("📈 Gastos por Categoria")
chart_data = df.groupby("categoria")["valor"].sum().reset_index()
st.bar_chart(chart_data, x="categoria", y="valor")

df.to_csv("gastos.csv", index=False)
with open("gastos.csv", "rb") as f:
    st.download_button(label="📥 Baixar CSV", data=f, file_name="gastos.csv", mime="text/csv")

conn.close()