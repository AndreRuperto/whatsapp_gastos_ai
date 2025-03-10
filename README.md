# README - IA para Controle de Gastos via WhatsApp

## 📌 Descrição
Este projeto consiste em uma IA que permite o registro de gastos via WhatsApp, ajudando no controle financeiro através de alertas e relatórios interativos. O sistema recebe mensagens, armazena as despesas e gera um **dashboard interativo** com insights sobre os gastos.

## 🚀 Funcionalidades
- 📲 **Registro de Gastos pelo WhatsApp**
- 📊 **Dashboard interativo para análise de despesas**
- ⚠️ **Alertas de limite de orçamento**
- 📅 **Relatórios semanais e mensais**
- 🔎 **Classificação automática de categorias de gastos**
- 📄 **Exportação de dados para CSV/Excel/Google Sheets**
- 🔍 **Leitura de notas fiscais via OCR (Opcional)**

## 🛠 Tecnologias Utilizadas
- **API do WhatsApp** (Twilio)
- **Python (FastAPI/Flask)**
- **Banco de Dados (SQLite, MySQL, Firebase)**
- **Streamlit (Dashboard de Gastos)**
- **Machine Learning (spaCy/NLTK para NLP)**
- **OCR (Tesseract ou EasyOCR para notas fiscais)**

## 📂 Estrutura do Projeto
```
whatsapp_gastos_ai/
┣ 📂 backend/      # API para processar mensagens do WhatsApp
┣ 📂 database/     # Banco de dados para armazenar os gastos
┣ 📂 dashboard/    # Dashboard interativo com gráficos
┣ 📂 notebook/     # Scripts para NLP e análise de dados
┣ 📄 requirements.txt  # Dependências do projeto
┣ 📄 README.md     # Documentação do projeto
┗ 📄 .gitignore    # Arquivos ignorados pelo Git
```

## 📌 Como Executar o Projeto
### 1️⃣ Clonar o repositório:
```bash
git clone https://github.com/seu-usuario/whatsapp_gastos_ai.git
cd whatsapp_gastos_ai
```

### 2️⃣ Instalar as dependências:
```bash
pip install -r requirements.txt
```

### 3️⃣ Configurar credenciais do Twilio (para WhatsApp):
Criar um arquivo `.env` com as credenciais:
```
TWILIO_ACCOUNT_SID=seu_sid
TWILIO_AUTH_TOKEN=seu_token
TWILIO_WHATSAPP_NUMBER=+seu_numero
```

### 4️⃣ Rodar o backend:
```bash
python backend/main.py
```

### 5️⃣ Rodar o dashboard:
```bash
streamlit run dashboard/app.py
```

## 📈 Exemplo de Uso
O usuário pode enviar mensagens como:
- `"Almoço 25.90"` → Salva a despesa na categoria **Alimentação**
- `"Uber 50"` → Salva na categoria **Transporte**
- `"Total gasto no mês?"` → Retorna o saldo atual do mês

## 🚀 Próximos Passos
- [ ] Criar o backend para receber mensagens do WhatsApp
- [ ] Configurar a API Twilio
- [ ] Criar banco de dados para armazenar os gastos
- [ ] Desenvolver o dashboard com gráficos
- [ ] Implementar alertas e relatórios

## 🔗 Contato
Projeto desenvolvido por **André Ruperto**. Contribuições são bem-vindas! 😊