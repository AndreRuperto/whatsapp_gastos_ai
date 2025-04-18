import os
import cv2
import numpy as np
import re
import pytesseract
import pdfplumber
from pyzbar.pyzbar import decode as pyzbar_decode
from pyzxing import BarCodeReader
from PIL import Image, ImageDraw, ImageFont
import io
from pdf2image import convert_from_path
import contextlib
from time import sleep
import logging

logger = logging.getLogger(__name__)

# # Configuração para ambiente local - ajuste para o Docker se necessário
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
# poppler_path = r"C:\poppler\Library\bin"

@contextlib.contextmanager
def suprimir_saida_pdfminer():
    with open(os.devnull, 'w') as fnull:
        with contextlib.redirect_stderr(fnull):
            yield

def extrair_nfe_tudo(texto):
    # Limpeza básica
    texto = re.sub(r'[ \t]+', ' ', texto)
    texto = re.sub(r'\n+', '\n', texto).strip()
    dados = {}

    # ------------------------------------------------
    # 1) Blocos de cabeçalho que você já tinha
    # ------------------------------------------------
    bloco1 = re.search(r'Chave de Acesso\s+Número\s+NF-e\s+Versão\s*\n([^\n]+)', texto, re.IGNORECASE)
    if bloco1:
        parts = bloco1.group(1).strip().split()
        chave_limpa = re.sub(r'[.\-/]', '', parts[0]) if parts else ''
        dados['chave_acesso'] = chave_limpa if chave_limpa else 'Não encontrado'
    else:
        dados['chave_acesso'] = 'Não encontrado'

    bloco2 = re.search(r'Modelo Série Número Data de Emissão.*\n([^\n]+)', texto, re.IGNORECASE)
    if bloco2:
        parts = bloco2.group(1).strip().split()
        dados['modelo'] = parts[0] if len(parts) > 0 else 'Não encontrado'
        dados['serie'] = parts[1] if len(parts) > 1 else 'Não encontrado'
        dados['numero'] = parts[2] if len(parts) > 2 else 'Não encontrado'
        dados['data_emissao'] = parts[3] if len(parts) > 3 else 'Não encontrado'
        dados['hora_emissao'] = parts[4] if len(parts) > 4 else 'Não encontrado'
        dados['data_saida'] = parts[5] if len(parts) > 5 else 'Não encontrado'
        dados['hora_saida'] = parts[6] if len(parts) > 6 else 'Não encontrado'
        dados['valor_total_nota'] = parts[7] if len(parts) > 7 else 'Não encontrado'
    else:
        for campo in ['modelo', 'serie', 'numero', 'data_emissao', 'hora_emissao', 'data_saida', 'hora_saida', 'valor_total_nota']:
            dados[campo] = 'Não encontrado'

    bloco_emitente = re.search(r'Emitente\s*\nCNPJ.*?\n([^\n]+)', texto, re.IGNORECASE)
    if bloco_emitente:
        parts = bloco_emitente.group(1).strip().split()
        cnpj = parts[0] if parts else ''
        uf = parts[-1] if len(parts) >= 1 else ''
        ie = parts[-2] if len(parts) >= 2 else ''
        nome = ' '.join(parts[1:-2]) if len(parts) > 3 else ''
        dados.update({
            'emitente_cnpj': cnpj,
            'emitente_ie': ie,
            'emitente_uf': uf,
            'emitente_nome': nome.strip() if nome else 'Não encontrado'
        })
    else:
        for campo in ['emitente_cnpj', 'emitente_ie', 'emitente_uf', 'emitente_nome']:
            dados[campo] = 'Não encontrado'

    bloco_dest = re.search(r'Destinatário\s*\nCPF.*?\n([^\n]+)', texto, re.IGNORECASE)
    if bloco_dest:
        parts = bloco_dest.group(1).strip().split()
        cpf = parts[0] if parts else ''
        uf = parts[-1] if len(parts) >= 1 else ''
        nome = ' '.join(parts[1:-1]) if len(parts) > 2 else ''
        dados.update({
            'destinatario_cpf': cpf,
            'destinatario_uf': uf,
            'destinatario_nome': nome.strip() if nome else 'Não encontrado'
        })
    else:
        for campo in ['destinatario_cpf', 'destinatario_uf', 'destinatario_nome']:
            dados[campo] = 'Não encontrado'

    bloco_nat = re.search(r'Natureza da Operação.*\n([^\n]+)', texto, re.IGNORECASE)
    if bloco_nat:
        line = bloco_nat.group(1).strip()
        nat_op = re.search(r'^(.*?)\s+(\d\s*-\s*\S+)\s+(.*)$', line)
        if nat_op:
            dados.update({
                'natureza_operacao': nat_op.group(1).strip(),
                'tipo_operacao': nat_op.group(2).strip(),
            })
        else:
            dados['natureza_operacao'] = line
            dados['tipo_operacao'] = 'Não encontrado'
    else:
        dados['natureza_operacao'] = 'Não encontrado'
        dados['tipo_operacao'] = 'Não encontrado'

    situacao = re.search(r'Situação Atual:\s*(.+)', texto, re.IGNORECASE)
    dados['situacao_atual'] = situacao.group(1).strip() if situacao else 'Não encontrado'

    evento = re.search(r'Autorização de Uso\s+(\d+)\s+([\d/]+ às [\d:.-]+)\s+([\d/]+ às [\d:.-]+)', texto)
    if evento:
        dados.update({
            'protocolo_autorizacao': evento.group(1),
            'data_autorizacao': evento.group(2),
            'data_inclusao': evento.group(3)
        })
    else:
        dados['protocolo_autorizacao'] = 'Não encontrado'
        dados['data_autorizacao'] = 'Não encontrado'
        dados['data_inclusao'] = 'Não encontrado'

    match_secao = re.search(r'(?s)Formas de Pagamento\s*(.*?)(?=\n[ A-Z][a-zA-Z]|$)', texto, flags=re.IGNORECASE)
    if match_secao:
        bloco_pagto = match_secao.group(1)
        desc_meio_match = re.search(r'Descriç[aã]o\s+do\s+Meio\s+de\s+Pagamento\s+(.+)', bloco_pagto, re.IGNORECASE)
        descricao_meio_pagamento = desc_meio_match.group(1).strip() if desc_meio_match else 'Não encontrado'
        dados['descricao_meio_pagamento'] = descricao_meio_pagamento
    else:
        dados['descricao_meio_pagamento'] = 'Não encontrado'

    # ------------------------------------------------
    # 2) Pegar os produtos a partir de "Dados dos Produtos e Serviços"
    # ------------------------------------------------
    # Para encontrar o bloco, procuramos a substring entre
    # "Dados dos Produtos e Serviços" e "Totais" (ou "Dados do Transporte").
    # Ajuste conforme sua estrutura real.
    bloco_produto_match = re.search(
        r'Dados dos Produtos e Serviços\s*(.*?)\n\s*(Totais|Dados do Transporte|$)',
        texto,
        flags=re.IGNORECASE | re.DOTALL
    )

    lista_produtos = []
    if bloco_produto_match:
        bloco_produtos = bloco_produto_match.group(1)
        linhas = bloco_produtos.splitlines()
        
        # Regex para extrair: número do item, descrição, quantidade, unidade e valor
        padrao_produto = re.compile(
            r'^(\d+)\s+(.+)\s+(\d[\d.,]*)\s+([A-Za-z]+)\s+(\d[\d.,]*)\s*$'
        )

        # Percorre todas as linhas do bloco de produtos
        for idx, linha_produto in enumerate(linhas):
            linha_produto = linha_produto.strip()
            if not linha_produto:
                continue  # pula linhas vazias

            match_prod = padrao_produto.match(linha_produto)
            if match_prod:
                numero_item = match_prod.group(1)
                descricao   = match_prod.group(2).strip()
                quantidade  = match_prod.group(3)
                unidade     = match_prod.group(4)
                valor       = match_prod.group(5)

                lista_produtos.append({
                    "numero_item": numero_item,
                    "descricao": descricao,
                    "quantidade": quantidade,
                    "unidade": unidade,
                    "valor": valor
                })

    # Depois do loop, guarda no dicionário final
    dados["produtos"] = lista_produtos

    return dados


def extrair_produtos(texto):
    # Permite que haja linhas em branco entre o nome do produto e a linha de qtd x unit x total
    padrao_linha_produto = re.compile(
        r'(\d+)\s*[-—]+\s*(.+?)\s*\n+\s*([\d.,]+)\s*x\s*([\d.,]+)\s+([\d.,]+)',
        re.IGNORECASE
    )

    produtos = []
    for match in padrao_linha_produto.finditer(texto):
        codigo = match.group(1).strip()
        nome = match.group(2).strip()
        qtd = match.group(3).strip()
        unitario = match.group(4).strip()
        total = match.group(5).strip()

        # Exemplo de correção de casos tipo "045" => "0,45" se você realmente quiser corrigir manualmente
        if re.match(r'^0+\d+$', qtd):
            if len(qtd) > 1:
                qtd = '0,' + qtd.lstrip('0')

        produtos.append({
            "codigo": codigo,
            "nome": nome,
            "quantidade": qtd,
            "unitario": unitario,
            "total": total
        })

    return produtos

def rotate_image(image, angle):
    (h, w) = image.shape[:2]
    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(image, matrix, (w, h))

def decode_opencv(img_bgr):
    detector = cv2.QRCodeDetector()
    data, _, _ = detector.detectAndDecode(img_bgr)
    return data

def decode_pyzxing(img_path):
    reader = BarCodeReader()
    results = reader.decode(img_path)
    if not results:
        return None
    return results[0].get('parsed') or results[0].get('raw')

def apply_morphology(img, operation):
    kernel = np.ones((2, 2), np.uint8)
    if operation == "erode":
        return cv2.erode(img, kernel, iterations=1)
    elif operation == "dilate":
        return cv2.dilate(img, kernel, iterations=1)
    elif operation == "open":
        return cv2.morphologyEx(img, cv2.MORPH_OPEN, kernel)
    elif operation == "close":
        return cv2.morphologyEx(img, cv2.MORPH_CLOSE, kernel)
    return img

def try_all_techniques(img_path, i):
    original_color = cv2.imread(img_path, cv2.IMREAD_COLOR)
    if original_color is None:
        print(f"❌ Não foi possível carregar a imagem: {img_path}")
        return None

    original_gray = cv2.cvtColor(original_color, cv2.COLOR_BGR2GRAY)

    angles = [0, 90, 180, 270]
    thresholds = ["otsu", 50, 100, 150, 200]
    morphological_ops = [None, "erode", "dilate", "open", "close"]

    for angle in angles:
        rotated_color = rotate_image(original_color, angle)
        rotated_gray = rotate_image(original_gray, angle)

        for thresh_val in thresholds:
            gray_for_thresh = rotated_gray.copy()
            if thresh_val == "otsu":
                _, binarizada = cv2.threshold(gray_for_thresh, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            else:
                _, binarizada = cv2.threshold(gray_for_thresh, thresh_val, 255, cv2.THRESH_BINARY)

            for morph_op in morphological_ops:
                morphed = apply_morphology(binarizada, morph_op)
                final_bgr = cv2.cvtColor(morphed, cv2.COLOR_GRAY2BGR)

                # 1️⃣ Tenta primeiro com Pyzbar
                results_pyzbar = pyzbar_decode(Image.fromarray(morphed))
                if results_pyzbar:
                    print(f"[pyzbar] ✅ angle={angle}, thresh={thresh_val}, morph={morph_op}")
                    data = results_pyzbar[0].data.decode("utf-8")
                    tipo = results_pyzbar[0].type
                    return extrair_info_qrcode(data, tipo)

                # 2️⃣ Depois tenta OpenCV
                data_opencv = decode_opencv(final_bgr)
                if data_opencv:
                    print(f"[OpenCV] ✅ angle={angle}, thresh={thresh_val}, morph={morph_op}")
                    tipo = detectar_tipo_codigo(data_opencv)
                    return extrair_info_qrcode(data_opencv, tipo)

                # 3️⃣ Por fim tenta Pyzxing
                temp_path = f"temp{i}.png"
                cv2.imwrite(temp_path, morphed)
                data_pyzxing = decode_pyzxing(temp_path)
                if data_pyzxing:
                    print(f"[pyzxing] ✅ angle={angle}, thresh={thresh_val}, morph={morph_op}")
                    if isinstance(data_pyzxing, bytes):
                        data_pyzxing = data_pyzxing.decode('utf-8', errors='ignore')

                    tipo = detectar_tipo_codigo(data_pyzxing)
                    chave_match = re.search(r'(\d{44})', data_pyzxing)
                    if chave_match:
                        chave = chave_match.group(1)
                        consulta_url = f"https://ww1.receita.fazenda.df.gov.br/DecVisualizador/Nfce/Captcha?Chave={chave}"
                        return {
                            "tipo": tipo,
                            "url_qrcode": data_pyzxing,
                            "chave": chave,
                            "consulta_url": consulta_url
                        }

    print("🚫 Não foi possível decodificar o QR Code com nenhuma das heurísticas.")
    return None

def detectar_tipo_codigo(data):
    data = data.lower()
    if "http" in data:
        return "QRCODE"
    elif re.match(r"^\d{44}$", data):
        return "CODE128"
    else:
        return "Desconhecido"

def extrair_info_qrcode(qr_url, tipo_dado):
    if isinstance(qr_url, bytes):
        qr_url = qr_url.decode('utf-8')
    print(f"🔍 URL: {qr_url}")
    chave_match = re.search(r'(\d{44})', qr_url)
    if not chave_match:
        print("❌ Chave da nota não encontrada.")
        return None
    chave = chave_match.group(1)
    print(f"🧾 Chave da NFC-e: {chave}")
    consulta_url = f"https://ww1.receita.fazenda.df.gov.br/DecVisualizador/Nfce/Captcha?Chave={chave}"
    print(f"🌐 URL de consulta: {consulta_url}")
    return {
        "tipo": tipo_dado,
        "url_qrcode": qr_url,
        "chave": chave,
        "consulta_url": consulta_url
    }

def processar_qrcode_com_ocr(caminho_pdf):
    imagens = convert_from_path(caminho_pdf)
    imagens[0].save("pagina1.png", "PNG")
    texto = pytesseract.image_to_string(Image.open("pagina1.png"), lang='por')

    loja = re.search(r'^([A-ZÇÃ\s&]+(?:EIRELI|LTDA|ME|EPP|S\.A\.?))', texto, re.MULTILINE)
    cnpj = re.search(r'CNPJ:\s?([\d./-]+)', texto)
    produto = re.search(r'\d{3}\s+(.+?)\n', texto)
    valor = re.search(r'Total Cupom\s+R\$ ([\d,]+)', texto)
    pagamento = re.search(
        r'(Cart[aã]o\s+de\s+(Cr[eé]dito|D[eé]bito)|PIX|Dinheiro|Transfer[eê]ncia|Vale\s+(Alimenta[cç][aã]o|Refei[cç][aã]o))',
        texto,
        re.IGNORECASE
    )
    emissao = re.search(r'Emissão:\s*(\d{2}/\d{2}/\d{4} \d{2}:\d{2})', texto)
    chave = re.search(r'(\d{44})', texto)

    produtos = extrair_produtos(texto)

    texto_whatsapp = (
        f"🏪 Loja: {loja.group(1).strip() if loja else 'Não encontrado'}\n"
        f"🧾 CNPJ: {cnpj.group(1) if cnpj else 'Não encontrado'}\n"
        f"\n🛒 Produtos:\n"
    )
    
    for p in produtos:
        texto_whatsapp += f"📦 Produto: {p['nome']} | Qtd: {p['quantidade']} | Unit: R$ {p['unitario']} | Total: R$ {p['total']}\n"
    
    texto_whatsapp += f"\n💰 Total: R$ {valor.group(1) if valor else 'Não encontrado'}\n"
    texto_whatsapp += f"💳 Pagamento: {pagamento.group(1).strip() if pagamento else 'Não encontrado'}\n"
    texto_whatsapp += f"🕒 Emissão: {emissao.group(1) if emissao else 'Não encontrado'}\n"

    return {
        "emitente_nome": loja.group(1).strip() if loja else "Não encontrado",
        "valor_total_nota": valor.group(1) if valor else "0",
        "forma_pagamento": pagamento.group(1).strip() if pagamento else "Não encontrado",
        "produtos": produtos,
        "texto_formatado": texto_whatsapp
    }

def formatar_qrcode_para_whatsapp(dados):
    texto_whatsapp = "📝 *Comprovante de compra detectado:*\n\n"
    
    # Adicionar informações da loja
    texto_whatsapp += f"🏪 Loja: {dados.get('emitente_nome', 'Não identificada')}\n"
    
    # Adicionar produtos
    texto_whatsapp += "\n📋 *Produtos:*\n"
    produtos = dados.get('produtos', [])
    for p in produtos:
        nome = p.get('nome', p.get('descricao', 'Produto'))
        qtd = p.get('quantidade', '1')
        unit = p.get('unitario', '0')
        total = p.get('total', '0')
        texto_whatsapp += f"📦 {nome} | Qtd: {qtd} | Unit: R$ {unit} | Total: R$ {total}\n"
    
    # Adicionar valor total e forma de pagamento
    texto_whatsapp += f"\n💰 Total: R$ {dados.get('valor_total_nota', '0')}\n"
    texto_whatsapp += f"💳 Pagamento: {dados.get('forma_pagamento', 'Não identificado')}\n"
    
    return texto_whatsapp

def formatar_codigodebarras_para_whatsapp(dados):
    """
    Formata os dados de um código de barras para envio via WhatsApp,
    usando emojis e formatação apropriada.
    """
    texto = "🧾 *NOTA FISCAL ELETRÔNICA*\n\n"
    
    # Dados básicos
    texto += f"🔑 Chave de Acesso: {dados['chave_acesso']}\n"
    texto += f"📄 Modelo: {dados['modelo']} | Série: {dados['serie']} | Número: {dados['numero']}\n"
    texto += f"🕒 Emissão: {dados['data_emissao']} {dados['hora_emissao']} | Saída: {dados['data_saida']} {dados['hora_saida']}\n\n"
    
    # Lista de produtos
    produtos = dados.get('produtos', [])
    if produtos:
        texto += "*📋 PRODUTOS:*\n"
        for p in produtos:
            texto += (
                f"🛒 {p['descricao']}\n"
                f"    Qtd: {p['quantidade']} {p['unidade']} | "
                f"Valor: R$ {p['valor']}\n"
            )
        texto += "\n"
    
    # Dados financeiros
    texto += f"💰 *VALOR TOTAL: R$ {dados['valor_total_nota']}*\n\n"
    
    # Dados da empresa
    texto += f"🏢 Emitente: {dados['emitente_nome']}\n"
    texto += f"📝 CNPJ: {dados['emitente_cnpj']} | IE: {dados['emitente_ie']} | UF: {dados['emitente_uf']}\n\n"
    
    # Dados do destinatário
    texto += f"👤 Destinatário: {dados['destinatario_nome']}\n"
    texto += f"🪪 CPF: {dados['destinatario_cpf']} | UF: {dados['destinatario_uf']}\n\n"
    
    # Informações adicionais
    texto += f"📦 Natureza: {dados['natureza_operacao']} | Tipo: {dados['tipo_operacao']}\n"
    texto += f"💳 Pagamento: {dados['descricao_meio_pagamento']}\n"
    texto += f"📌 Situação: {dados['situacao_atual']}\n"
    texto += f"📨 Protocolo: {dados['protocolo_autorizacao']}\n"
    texto += f"📅 Autorizado em: {dados['data_autorizacao']}\n"
    
    return texto

def processar_codigodebarras_com_pdfplumber(caminho_pdf):
    with suprimir_saida_pdfminer():
        with pdfplumber.open(caminho_pdf) as pdf:
            texto = "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])
    return extrair_nfe_tudo(texto)

def gerar_descricao_para_classificacao(dados, produtos=None):
    loja = dados.get("emitente_nome", "Loja não identificada")
    valor = dados.get("valor_total_nota", "0").replace("R$", "").strip()
    forma_pagamento = dados.get("forma_pagamento") or dados.get("descricao_meio_pagamento") or "forma não informada"
    if produtos is None:
        produtos = dados.get("produtos", [])
    if not produtos:
        descricao_produtos = "produto não identificado"
    else:
        nomes_prod = [p.get("descricao") or p.get("nome", "produto").lower() for p in produtos]
        descricao_produtos = " ".join(nomes_prod)
    return f"compra na loja {loja.lower()} {descricao_produtos} valor {valor} pago com {forma_pagamento.lower()}"

def gerar_imagem_tabela(dados, tipo_documento=None):
    """
    Gera uma imagem com a tabela de produtos usando Pillow.
    
    Args:
        dados (dict): Dicionário com dados extraídos do documento
        tipo_documento (str, optional): "nfe" para nota fiscal eletrônica ou 
                                       "cupom" para cupom fiscal/QR code
                                       
    Returns:
        str: Caminho para a imagem gerada ou None em caso de erro
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
        import os
        import uuid
        
        # Se tipo_documento não foi fornecido, tentar detectar
        if not tipo_documento:
            if 'chave_acesso' in dados and dados['chave_acesso'] != 'Não encontrado':
                tipo_documento = "nfe"
            else:
                tipo_documento = "cupom"
                
        logger.info(f"Gerando imagem para documento tipo: {tipo_documento}")
        
        # Obter lista de produtos conforme o tipo
        produtos = dados.get('produtos', [])
        if not produtos:
            logger.warning("Nenhum produto encontrado nos dados para gerar imagem")
            return None
            
        # Definir tamanho da imagem
        largura = 800
        altura = 200 + (len(produtos) * 35) + 150  # Espaço extra para cabeçalho e rodapé
        
        # Criar imagem com fundo branco
        imagem = Image.new('RGB', (largura, altura), color=(255, 255, 255))
        desenho = ImageDraw.Draw(imagem)
        
        # Tentar carregar fonte, ou usar fonte padrão
        try:
            # Fontes comuns em ambientes Docker/Linux
            fontes_possiveis = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                "/usr/share/fonts/TTF/DejaVuSans.ttf",
            ]
            
            # Tentar carregar qualquer uma das fontes
            fonte_titulo = None
            for fonte in fontes_possiveis:
                if os.path.exists(fonte):
                    fonte_titulo = ImageFont.truetype(fonte, 22)
                    fonte_header = ImageFont.truetype(fonte, 18)
                    fonte_normal = ImageFont.truetype(fonte, 16)
                    break
                    
            # Se nenhuma fonte foi encontrada, usar fonte padrão
            if not fonte_titulo:
                fonte_titulo = ImageFont.load_default()
                fonte_header = ImageFont.load_default()
                fonte_normal = ImageFont.load_default()
                
        except Exception as e:
            logger.warning(f"Erro ao carregar fontes: {e}. Usando fontes padrão.")
            fonte_titulo = ImageFont.load_default()
            fonte_header = ImageFont.load_default()
            fonte_normal = ImageFont.load_default()
        
        # Desenhar cabeçalho específico conforme o tipo
        y = 20
        
        if tipo_documento == "nfe":
            desenho.text((20, y), "NOTA FISCAL ELETRÔNICA", fill=(0, 0, 0), font=fonte_titulo)
            y += 40
            
            emitente = dados.get('emitente_nome', 'Emissor não identificado')
            desenho.text((20, y), f"Emitente: {emitente}", fill=(0, 0, 0), font=fonte_normal)
            y += 25
            
            cnpj = dados.get('emitente_cnpj', 'N/A')
            desenho.text((20, y), f"CNPJ: {cnpj}", fill=(0, 0, 0), font=fonte_normal)
            y += 25
            
            chave = dados.get('chave_acesso', 'N/A')
            if len(chave) > 20:
                chave = f"{chave[:15]}...{chave[-5:]}"
            desenho.text((20, y), f"Chave: {chave}", fill=(0, 0, 0), font=fonte_normal)
            y += 25
            
            data_emissao = f"{dados.get('data_emissao', '')} {dados.get('hora_emissao', '')}"
            desenho.text((20, y), f"Emissão: {data_emissao}", fill=(0, 0, 0), font=fonte_normal)
            
        else:  # cupom fiscal
            desenho.text((20, y), "CUPOM FISCAL", fill=(0, 0, 0), font=fonte_titulo)
            y += 40
            
            # Para cupom fiscal, os dados podem vir de regex
            loja = None
            if 'emitente_nome' in dados:
                loja = dados.get('emitente_nome')
            elif hasattr(dados, 'get') and 'loja' in dados:
                loja = dados.get('loja')
                
            if isinstance(loja, str):
                desenho.text((20, y), f"Loja: {loja}", fill=(0, 0, 0), font=fonte_normal)
            elif hasattr(loja, 'group'):
                desenho.text((20, y), f"Loja: {loja.group(1).strip() if loja else 'Não identificada'}", 
                             fill=(0, 0, 0), font=fonte_normal)
            else:
                desenho.text((20, y), "Loja: Não identificada", fill=(0, 0, 0), font=fonte_normal)
            y += 25
            
            # CNPJ
            cnpj = None
            if 'cnpj' in dados:
                cnpj = dados.get('cnpj')
                
            if isinstance(cnpj, str):
                desenho.text((20, y), f"CNPJ: {cnpj}", fill=(0, 0, 0), font=fonte_normal)
            elif hasattr(cnpj, 'group'):
                desenho.text((20, y), f"CNPJ: {cnpj.group(1) if cnpj else 'Não identificado'}", 
                             fill=(0, 0, 0), font=fonte_normal)
            else:
                desenho.text((20, y), "CNPJ: Não identificado", fill=(0, 0, 0), font=fonte_normal)
            y += 25
            
            # Data de emissão
            emissao = None
            if 'data_emissao' in dados:
                emissao = dados.get('data_emissao')
                
            if isinstance(emissao, str):
                desenho.text((20, y), f"Emissão: {emissao}", fill=(0, 0, 0), font=fonte_normal)
            elif hasattr(emissao, 'group'):
                desenho.text((20, y), f"Emissão: {emissao.group(1) if emissao else 'Não identificada'}", 
                             fill=(0, 0, 0), font=fonte_normal)
            
        # Espaço e linha divisória antes da tabela
        y += 40
        desenho.line([(20, y), (largura-20, y)], fill=(200, 200, 200), width=2)
        y += 10
        
        # Cabeçalho da tabela
        desenho.rectangle([(20, y), (largura-20, y+30)], fill=(230, 230, 230))
        desenho.text((30, y+5), "Produto", fill=(0, 0, 0), font=fonte_header)
        desenho.text((380, y+5), "Qtd", fill=(0, 0, 0), font=fonte_header)
        desenho.text((470, y+5), "Unit", fill=(0, 0, 0), font=fonte_header)
        desenho.text((600, y+5), "Total", fill=(0, 0, 0), font=fonte_header)
        
        # Desenhar linhas de produtos conforme o tipo
        y += 30
        total_geral = 0.0
        
        for produto in produtos:
            if tipo_documento == "nfe":
                nome = produto.get('descricao', 'Produto')
                qtd = produto.get('quantidade', '1')
                unidade = produto.get('unidade', '')
                valor = produto.get('valor', '0')
                
                # Calcular o total para cada item se não estiver presente
                try:
                    qtd_num = float(str(qtd).replace(',', '.'))
                    valor_num = float(str(valor).replace(',', '.'))
                    total_item = f"{qtd_num * valor_num:.2f}".replace('.', ',')
                except:
                    total_item = "0,00"
            else:
                # Para cupom fiscal
                nome = produto.get('nome', 'Produto')
                qtd = produto.get('quantidade', '1')
                unidade = ''
                valor = produto.get('unitario', '0')
                total_item = produto.get('total', '0')
            
            # Limitar tamanho do nome para caber na coluna
            if len(nome) > 30:
                nome = nome[:27] + "..."
            
            # Limpar formatação de preço
            if isinstance(valor, str):
                valor = valor.replace("R$", "").strip()
            if isinstance(total_item, str):
                total_item = total_item.replace("R$", "").strip()
            
            # Adicionar unidade à quantidade se disponível
            qtd_display = f"{qtd} {unidade}".strip() if unidade else qtd
            
            # Desenhar linha de produto
            desenho.text((30, y+5), nome, fill=(0, 0, 0), font=fonte_normal)
            desenho.text((380, y+5), str(qtd_display), fill=(0, 0, 0), font=fonte_normal)
            desenho.text((470, y+5), f"R$ {valor}", fill=(0, 0, 0), font=fonte_normal)
            desenho.text((600, y+5), f"R$ {total_item}", fill=(0, 0, 0), font=fonte_normal)
            
            # Calcular total geral
            try:
                valor_total = float(str(total_item).replace(',', '.'))
                total_geral += valor_total
            except:
                pass
            
            y += 35
            desenho.line([(20, y), (largura-20, y)], fill=(200, 200, 200), width=1)
        
        # Desenhar total do documento
        y += 15
        if tipo_documento == "nfe":
            total_nota = dados.get('valor_total_nota', str(total_geral))
        else:
            # Para cupom fiscal, o valor pode vir de regex
            valor = dados.get('valor_total_nota', str(total_geral))
            if hasattr(valor, 'group'):
                total_nota = valor.group(1) if valor else str(total_geral)
            else:
                total_nota = str(valor)
        
        # Limpar formatação do total
        if isinstance(total_nota, str):
            total_nota = total_nota.replace("R$", "").strip()
            
        desenho.rectangle([(largura-270, y), (largura-20, y+30)], fill=(240, 240, 240))
        desenho.text((largura-250, y+5), "TOTAL:", fill=(0, 0, 0), font=fonte_header)
        desenho.text((largura-150, y+5), f"R$ {total_nota}", fill=(0, 0, 0), font=fonte_header)
        
        # Adicionar informação de pagamento
        y += 45
        if tipo_documento == "nfe":
            pagamento = dados.get('descricao_meio_pagamento', 'Não identificado')
        else:
            pagamento = dados.get('forma_pagamento', 'Não identificado')
            if hasattr(pagamento, 'group'):
                pagamento = pagamento.group(1).strip() if pagamento else 'Não identificado'
                
        desenho.text((20, y+5), f"Pagamento: {pagamento}", fill=(0, 0, 0), font=fonte_normal)
        
        # Salvar em um arquivo temporário
        arquivo_temp = f"temp_comprovante_{uuid.uuid4()}.png"
        imagem.save(arquivo_temp)
        
        # Configurar limpeza automática após algum tempo
        import threading
        def limpar_arquivo():
            try:
                if os.path.exists(arquivo_temp):
                    os.remove(arquivo_temp)
                    logger.info(f"Arquivo temporário {arquivo_temp} removido com sucesso.")
            except Exception as e:
                logger.error(f"Erro ao remover arquivo temporário: {e}")
                
        # Agendar limpeza após 5 minutos
        t = threading.Timer(300, limpar_arquivo)
        t.daemon = True
        t.start()
        
        return arquivo_temp
        
    except Exception as e:
        logger.exception(f"Erro ao gerar imagem da tabela: {e}")
        return None