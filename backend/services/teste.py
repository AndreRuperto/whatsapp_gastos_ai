import logging
import requests
import json
import os


BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # Obtém o diretório do script atual
MOEDAS_FILE = os.path.join(BASE_DIR, "..", "data", "moedas.json")

print(MOEDAS_FILE)