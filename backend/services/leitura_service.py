import os
import cv2
import numpy as np
import re
import pytesseract
import pdfplumber
from pyzbar.pyzbar import decode as pyzbar_decode
from pyzxing import BarCodeReader
from PIL import Image
from pdf2image import convert_from_path
import contextlib
from time import sleep

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

    print(f"🏪 Loja: {loja.group(1).strip() if loja else 'Não encontrado'}")
    print(f"🧾 CNPJ: {cnpj.group(1) if cnpj else 'Não encontrado'}")
    for p in produtos:
        print(f"🛒 Produto: {p['nome']} | Qtd: {p['quantidade']} | Unit: R$ {p['unitario']} | Total: R$ {p['total']}")
    print(f"💰 Total: R$ {valor.group(1) if valor else 'Não encontrado'}")
    print(f"💳 Pagamento: {pagamento.group(1).strip() if pagamento else 'Não encontrado'}")
    print(f"🕒 Emissão: {emissao.group(1) if emissao else 'Não encontrado'}")
    print(f"🔑 Chave: {chave.group(1) if chave else 'Não encontrado'}")

    return {
        "emitente_nome": loja.group(1).strip() if loja else "Não encontrado",
        "valor_total_nota": valor.group(1) if valor else "0",
        "forma_pagamento": pagamento.group(1).strip() if pagamento else "Não encontrado",
        "produtos": produtos
    }

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

def print_formatado(dados):
    # Imprime dados básicos
    print(f"🔑 Chave de Acesso: {dados['chave_acesso']}")
    print(f"🧾 Modelo: {dados['modelo']} | Série: {dados['serie']} | Número: {dados['numero']}")
    print(f"🕒 Emissão: {dados['data_emissao']} {dados['hora_emissao']} | Saída: {dados['data_saida']} {dados['hora_saida']}")
    
    # Lista de produtos
    produtos = dados.get('produtos', [])

    # Se quisermos imprimir todos os itens de produtos
    for p in produtos:
        print(
            f"🛒 Número Item: {p['numero_item']} | "
            f"Produto: {p['descricao']} | "
            f"Qtd: {p['quantidade']} | "
            f"Unidade: {p['unidade']} | "
            f"Valor: R$ {p['valor']}"
        )
    
    # Imprime demais dados da NF-e
    print(f"💰 Valor Total: R$ {dados['valor_total_nota']}")
    print(f"🏢 Emitente: {dados['emitente_nome']} | CNPJ: {dados['emitente_cnpj']} | IE: {dados['emitente_ie']} | UF: {dados['emitente_uf']}")
    print(f"👤 Destinatário: {dados['destinatario_nome']} | CPF: {dados['destinatario_cpf']} | UF: {dados['destinatario_uf']}")
    print(f"📦 Natureza: {dados['natureza_operacao']} | Tipo: {dados['tipo_operacao']}")
    print(f"💳 Pagamento: {dados['descricao_meio_pagamento']}")
    print(f"📌 Situação: {dados['situacao_atual']}")
    print(f"📨 Protocolo: {dados['protocolo_autorizacao']}")
    print(f"📅 Autorizado em: {dados['data_autorizacao']} | Inclusão: {dados['data_inclusao']}")
