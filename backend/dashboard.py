import streamlit as st
import pandas as pd
import psycopg2
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
import pytz
from services.token_service import validar_token
import altair as alt

load_dotenv()

st.set_page_config(page_title="Dashboard Financeiro", layout="wide")
st.title("📊 Dashboard de Gastos - WhatsApp AI")
st.markdown("---")

query_params = st.query_params
phone = query_params.get("phone")
token = query_params.get("token")

resultado = validar_token(phone, token)
if not resultado:
    st.error("🔒 Link inválido ou expirado. Solicite um novo link.")
    st.stop()

schema, expira_em = resultado

# 🎯 Alerta de expiração com fuso de Brasília
fuso_brasilia = pytz.timezone("America/Sao_Paulo")
agora = datetime.now(fuso_brasilia)
expira_em = expira_em.astimezone(fuso_brasilia)  # Exibe no fuso correto

minutos_restantes = int((expira_em - agora).total_seconds() // 60)
expira_formatado = expira_em.strftime("%H:%M")

if minutos_restantes <= 0:
    st.error("❌ Este link já expirou. Por favor, solicite um novo.")
    st.stop()
elif minutos_restantes <= 5:
    st.warning(f"⚠️ Seu link expira em {minutos_restantes} minutos (às {expira_formatado}). Salve os dados se necessário.")
else:
    st.info(f"🔐 Link válido até às {expira_formatado} (horário de Brasília).")

# 🔌 Conecta ao banco de dados e carrega as informações
DATABASE_URL = os.getenv("DATABASE_URL")
conn = psycopg2.connect(DATABASE_URL)
query = f"SELECT descricao, valor, categoria, meio_pagamento, data FROM {schema}.gastos ORDER BY data DESC"
df = pd.read_sql(query, conn)

st.subheader("💰 Últimos Gastos Registrados")
st.dataframe(df)

# ⚙️ Filtro por Categoria
categoria = st.selectbox("Filtrar por Categoria", ["Todas"] + list(df["categoria"].unique()))
if categoria != "Todas":
    df = df[df["categoria"] == categoria]

# 📅 Gráfico Temporal
st.subheader("📅 Gastos ao longo do tempo")
df["data"] = pd.to_datetime(df["data"])
df = df.copy()
df.set_index("data", inplace=True)
st.line_chart(df["valor"])

# 📈 Gráfico de Gastos por Categoria
st.subheader("📈 Gastos por Categoria")
chart_data_cat = df.groupby("categoria")["valor"].sum().reset_index()
st.bar_chart(chart_data_cat, x="categoria", y="valor")

# 💳 Gráfico de Gastos por Meio de Pagamento (débito, crédito, pix, etc.)
st.subheader("💳 Gastos por Meio de Pagamento")

# Cria um mini DataFrame com a soma dos valores por "meio_pagamento"
df_pagamento = df.groupby("meio_pagamento")["valor"].sum().reset_index()

# Deixa o usuário escolher qual gráfico quer ver
opcoes_grafico = ["Barra (nativo)", "Pizza (Altair)"]
tipo_grafico = st.selectbox("Escolha o tipo de gráfico:", opcoes_grafico)

if tipo_grafico == "Barra (nativo)":
    # st.bar_chart precisa de índice
    df_pagamento_bar = df_pagamento.copy()
    df_pagamento_bar.set_index("meio_pagamento", inplace=True)
    st.bar_chart(df_pagamento_bar["valor"])

elif tipo_grafico == "Pizza (Altair)":
    # Gráfico de Pizza usando Altair
    chart = alt.Chart(df_pagamento).mark_arc().encode(
        theta=alt.Theta(field="valor", type="quantitative"),
        color=alt.Color(field="meio_pagamento", type="nominal"),
        tooltip=["meio_pagamento", "valor"]
    )
    st.altair_chart(chart, use_container_width=True)

# 📥 Download CSV
df.to_csv("gastos.csv", index=False)
with open("gastos.csv", "rb") as f:
    st.download_button(label="📥 Baixar CSV", data=f, file_name="gastos.csv", mime="text/csv")

conn.close()