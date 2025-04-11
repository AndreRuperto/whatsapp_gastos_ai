from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
from datetime import datetime
from bs4 import BeautifulSoup
import time

# Setup do Selenium
def iniciar_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--log-level=3")
    options.add_experimental_option("excludeSwitches", ["enable-logging"])
    options.binary_location = "/usr/bin/google-chrome"  # Caminho fixo para o Chrome no Docker

    # Usando o chromedriver instalado manualmente via Docker
    service = Service("/usr/local/bin/chromedriver")
    return webdriver.Chrome(service=service, options=options)

# Função para converter HTML em texto simples para WhatsApp
def html_para_whatsapp_formatado(html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(["button", "a", "style", "script"]):
        tag.decompose()
    texto_formatado = soup.get_text(separator="\n", strip=True)
    return texto_formatado.strip()

# Extração baseada em blocos reais do texto
def extrair_blocos_pelo_titulo_bruto(texto):
    titulos = ["NA EDIÇÃO DE HOJE", "MUNDO", "BRASIL", "TECNOLOGIA", "STAT OF THE DAY", "RECADO DA EQUIPE"]
    indices = []

    for titulo in titulos:
        pos = texto.find(titulo)
        if pos != -1:
            indices.append((titulo, pos))

    indices.sort(key=lambda x: x[1])
    blocos = []
    for i in range(len(indices)):
        _, start = indices[i]
        end = indices[i + 1][1] if i + 1 < len(indices) else len(texto)
        conteudo = texto[start + len(titulos[i]):end].strip()
        blocos.append(conteudo if conteudo else "Conteúdo não encontrado.")

    return blocos

# Formatar texto para WhatsApp
def formatar_conteudo_para_whatsapp(data, blocos):
    manchete = "sem plateia\nbom dia. tem dias em que a maior conquista é fazer o que precisa ser feito mesmo sem ninguém vendo. sem aplauso, sem post, sem confete. só você com você mesmo."

    return f"""
🗞️ *the news*  
📅 *{data}*  
⏳ *Tempo de leitura estimado: 15-17 min*  

---

📝 *Manchete do Dia:*  
{manchete}

---

📌 *Na edição de hoje:*  
{blocos[0]}

---

🌎 *MUNDO*  
{blocos[1]}

---

🇧🇷 *BRASIL*  
{blocos[2]}

---

💻 *TECNOLOGIA*  
{blocos[3]}

---

📉 *STAT OF THE DAY*  
{blocos[4]}

---

📣 *RECADO DA EQUIPE*  
{blocos[5]}

---
"""

def obter_boletim_the_news():
    data_hoje = datetime.today().strftime("%d-%m-%Y")
    url = f"https://thenewscc.beehiiv.com/p/{data_hoje}"
    driver = iniciar_driver()
    driver.get(url)

    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, '/html/body/div[1]/div/main/div/div[3]/div[2]/div'))
        )
        time.sleep(1)
    except:
        print("❌ Não foi possível localizar as notícias.")
        driver.quit()
        exit()

    try:
        conteudo = driver.find_element(By.XPATH, '/html/body/div[1]/div/main/div/div[3]/div[2]/div')
        inner_html = conteudo.get_attribute("innerHTML")
        texto_formatado = html_para_whatsapp_formatado(inner_html)

        blocos = extrair_blocos_pelo_titulo_bruto(texto_formatado)
        data_pt = datetime.today().strftime("%d/%m/%Y")
        mensagem_whatsapp = formatar_conteudo_para_whatsapp(data_pt, blocos)

        print(mensagem_whatsapp)
    except Exception as e:
        print(f"⚠️ Erro ao tentar capturar o conteúdo: {e}")

    driver.quit()