web: uvicorn backend.main:app --host 0.0.0.0 --port $PORT
dashboard: streamlit run backend/dashboard.py --server.port $PORT --server.address 0.0.0.0
cron: python backend/atualizar_moedas.py
bot: node whatsapp_bot/server.js

apt-get update && cd whatsapp_bot && npm install && node server.js