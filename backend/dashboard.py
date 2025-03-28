import streamlit as st
import pandas as pd
import psycopg2
import os
from dotenv import load_dotenv
from services.token_service import validar_token

load_dotenv()

st.set_page_config(page_title="Dashboard Financeiro", layout="wide")
st.title("📊 Dashboard de Gastos - WhatsApp AI")
st.markdown("---")

query_params = st.experimental_get_query_params()
phone = query_params.get("phone", [None])[0]
token = query_params.get("token", [None])[0]

schema = validar_token(phone, token)
if not schema:
    st.error("🔒 Link inválido ou expirado. Solicite um novo link.")
    st.stop()

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
df.set_index("data", inplace=True)
st.line_chart(df["valor"])

st.subheader("📈 Gastos por Categoria")
chart_data = df.groupby("categoria")["valor"].sum().reset_index()
st.bar_chart(chart_data, x="categoria", y="valor")

df.to_csv("gastos.csv", index=False)
st.download_button(label="📥 Baixar CSV", data=open("gastos.csv", "rb"), file_name="gastos.csv", mime="text/csv")

conn.close()