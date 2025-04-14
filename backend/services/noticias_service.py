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
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--log-level=3")
    options.binary_location = "/usr/bin/google-chrome"

    # Use o caminho direto do ChromeDriver (já instalado no Docker)
    service = Service("/usr/local/bin/chromedriver")
    return webdriver.Chrome(service=service, options=options)

# Função para converter HTML em texto simples para WhatsApp
def formatar_titulo(texto: str) -> str:
    if "/" in texto and texto.count("/") == 2:
        return datetime.today().strftime("%d-%m-%Y")
    return texto.lower().replace(" ", "-")

def html_para_whatsapp_formatado(html):
    soup = BeautifulSoup(html, "html.parser")

    # Remove elementos visuais e desnecessários
    for tag in soup(["style", "script", "button", "header", "footer", "img", "svg"]):
        tag.decompose()

    # Negrito e itálico
    for bold in soup.find_all(['b', 'strong']):
        bold_text = bold.get_text()
        bold.replace_with(f"*{bold_text}*")

    for italic in soup.find_all(['i', 'em']):
        italic_text = italic.get_text()
        italic.replace_with(f"_{italic_text}_")

    # Substitui listas <li> por linha com traço (-)
    for li in soup.find_all("li"):
        li.string = f"- {li.get_text(strip=True)}"

    texto_formatado = soup.get_text(separator="\n", strip=True)
    return texto_formatado.strip()

def extrair_blocos_por_xpath(driver):
    blocos = []
    blocos_divs = driver.find_elements(By.XPATH, '//*[@id="content-blocks"]/div')

    for div in blocos_divs:
        try:
            titulo = div.find_element(By.XPATH, './div[1]/h5/span/b').text.strip().upper()
            conteudo = div.get_attribute("innerHTML")
            conteudo_formatado = html_para_whatsapp_formatado(conteudo)
            blocos.append((titulo, conteudo_formatado))
        except:
            continue
    return blocos

def formatar_conteudo_para_whatsapp(data, blocos):
    limite = 4096
    mensagens = []

    header = f"""
🗒️ *the news*  
📅 *{data}*  
⏳ *Tempo de leitura estimado: 15-17 min*  

---
""".strip()

    atual = header
    for titulo, conteudo in blocos:
        emoji = "🧹"
        if "MUNDO" in titulo:
            emoji = "🌎"
        elif "BRASIL" in titulo:
            emoji = "🇧🇷"
        elif "TECNOLOGIA" in titulo:
            emoji = "💻"
        elif "STAT" in titulo:
            emoji = "📉"
        elif "RECADO" in titulo:
            emoji = "📣"
        elif "MANCHETE" in titulo:
            emoji = "📝"
        elif "EDIÇÃO" in titulo:
            emoji = "📌"

        bloco = f"\n\n{emoji} *{titulo}*\n{conteudo}"

        if len(atual) + len(bloco) > limite:
            mensagens.append(atual.strip())
            atual = bloco
        else:
            atual += bloco

    mensagens.append(atual.strip())
    return mensagens

def obter_boletim_the_news():
    url = "https://thenewscc.beehiiv.com"
    driver = iniciar_driver()
    driver.get(url)

    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((
                By.XPATH,
                '/html/body/div[1]/div/main/div/div[4]/div/div/div/div/div[3]/div[1]/div[2]/div/a[1]/div/div[2]/h2'
            ))
        )
        time.sleep(1)

        titulo_elemento = driver.find_element(
            By.XPATH,
            '/html/body/div[1]/div/main/div/div[4]/div/div/div/div/div[3]/div[1]/div[2]/div/a[1]/div/div[2]/h2'
        )
        titulo_formatado = formatar_titulo(titulo_elemento.text)
        url_boletim = f"https://thenewscc.beehiiv.com/p/{titulo_formatado}"

        driver.get(url_boletim)

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "content-blocks"))
        )
        time.sleep(1)

        blocos = extrair_blocos_por_xpath(driver)
        if len(blocos) < 3:
            print("❌ Boletim incompleto ou estrutura inesperada.")
            print("🔎 Blocos encontrados:", [b[0] for b in blocos])
        else:
            data_pt = datetime.today().strftime("%d/%m/%Y")
            return formatar_conteudo_para_whatsapp(data_pt, blocos)

    except Exception as e:
        print(f"❌ Erro ao capturar o boletim: {e}")
    finally:
        driver.quit()