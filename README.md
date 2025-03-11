# 📌 WhatsApp Gastos AI
**Sistema de controle de gastos via WhatsApp, integrado com Twilio e armazenado no PostgreSQL (Railway).** 🚀  

---

## **📖 Visão Geral**
Este projeto permite que usuários registrem seus gastos diretamente via **WhatsApp**, armazenando os dados em um **banco de dados PostgreSQL** hospedado no **Railway**. 

✅ **Mensagens no WhatsApp** → ✅ **Webhook do Twilio** → ✅ **FastAPI** → ✅ **Banco de Dados (PostgreSQL no Railway)**

Os usuários podem enviar mensagens como:
```
Almoço 25.90
Uber 15.00
Mercado 120.50
```
E receberão uma confirmação automática:
```
Gasto de R$25.90 em 'Alimentação' registrado com sucesso!
```

Também é possível perguntar:
```
Total gasto no mês?
```
E o bot retorna o valor total gasto no mês.

---

## **🛠️ Tecnologias Utilizadas**
- **Python** + **FastAPI** (Backend)
- **Twilio API** (Integração com WhatsApp)
- **PostgreSQL** (Banco de dados no Railway)
- **Railway** (Deploy da API e banco de dados)
- **Ngrok** (Para testes locais do webhook)
- **Uvicorn** (Servidor ASGI)

---

## **🚀 Como Rodar o Projeto?**

### **1️⃣ Clonar o Repositório**
```bash
git clone https://github.com/seu-usuario/whatsapp_gastos_ai.git
cd whatsapp_gastos_ai
```

### **2️⃣ Criar e Ativar um Ambiente Virtual**
```bash
python -m venv venv
# Ativar no Windows
venv\Scripts\activate
# Ativar no Linux/macOS
source venv/bin/activate
```

### **3️⃣ Instalar as Dependências**
```bash
pip install -r requirements.txt
```

### **4️⃣ Criar o Arquivo `.env`**
Crie um arquivo `.env` na raiz do projeto e adicione suas credenciais:
```
TWILIO_ACCOUNT_SID=seu_sid_aqui
TWILIO_AUTH_TOKEN=seu_auth_token_aqui
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
DATABASE_URL=postgresql://usuario:senha@host:porta/database
```

**Obs:** No Railway, essas variáveis já foram configuradas via **"Shared Variables"**.

---

## **🌐 Como Configurar o Webhook no Twilio**
1️⃣ Acesse [Twilio Console](https://www.twilio.com/console).  
2️⃣ Vá para **Messaging** > **Sandbox for WhatsApp**.  
3️⃣ No campo **"When a message comes in"**, adicione sua API pública do Railway:  
   ```
   https://whatsappgastosai-production.up.railway.app/webhook
   ```
4️⃣ Defina **Method** como **POST**.  
5️⃣ Clique em **Save**.  

---

## **▶️ Como Iniciar o Servidor Localmente**
```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```
Agora você pode testar no navegador:
```
http://127.0.0.1:8000/docs
```

---

## **🚀 Como Rodar no Railway?**

### **1️⃣ Criar uma conta no Railway**
Caso ainda não tenha, crie uma conta gratuita no [Railway](https://railway.app/).  

### **2️⃣ Criar um novo projeto**
1. Acesse [Railway](https://railway.app/dashboard)
2. Clique em **"New Project"** e selecione **"Deploy from GitHub"**
3. Conecte o Railway ao repositório do **whatsapp_gastos_ai**
4. Aguarde a inicialização do serviço

### **3️⃣ Configurar as Variáveis de Ambiente**
1. No Railway, acesse a aba **"Variables"**
2. Adicione as seguintes variáveis:
   ```
   TWILIO_ACCOUNT_SID=seu_sid
   TWILIO_AUTH_TOKEN=seu_auth_token
   TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
   DATABASE_URL=postgresql://usuario:senha@host:porta/database
   ```
3. Salve as alterações

### **4️⃣ Criar um Banco de Dados no Railway**
1. No dashboard do Railway, clique em **"New Service"**
2. Escolha **PostgreSQL**
3. Copie a **DATABASE_URL** gerada e adicione às variáveis de ambiente

### **5️⃣ Criar o arquivo `Procfile`**
O `Procfile` indica ao Railway como rodar o servidor:
```
web: uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

### **6️⃣ Fazer o Deploy**
Se tudo estiver configurado corretamente, o Railway **detectará automaticamente** o projeto e iniciará o deploy.
Caso precise forçar um deploy manualmente:
```bash
railway up
```

### **7️⃣ Acessar a API pública no Railway**
Após o deploy, o Railway gera um domínio público:
```
https://whatsappgastosai-production.up.railway.app/docs
```
Esse link pode ser usado para testar a API no navegador.

---

## **📊 Próximos Passos**
- 📌 Criar um **dashboard interativo** com os gastos 📊
- 📌 Implementar **gráficos de categorias** de gastos 🎯
- 📌 Enviar **alertas de gastos altos** via WhatsApp 📲
- 📌 Adicionar **relatórios mensais automáticos** 📝
