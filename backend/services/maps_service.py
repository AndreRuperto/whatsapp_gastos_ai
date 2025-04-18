import requests
import os
from dotenv import load_dotenv
import logging

load_dotenv()
logger = logging.getLogger(__name__)

# API Key do OpenRouteService - você precisará se cadastrar em openrouteservice.org
ORS_API_KEY = os.getenv("ORS_API_KEY")

def calcular_rota(endereco_destino, lat_origem=None, lng_origem=None):
    """
    Calcula a rota entre a origem (ou localização atual) e o destino
    
    :param endereco_destino: Endereço do destino (texto)
    :param lat_origem: Latitude da origem (opcional)
    :param lng_origem: Longitude da origem (opcional)
    :return: Dicionário com distância, duração e URL para visualização no mapa
    """
    try:
        # 1. Geocodificar o endereço de destino
        geocode_url = f"https://api.openrouteservice.org/geocode/search"
        headers = {"Authorization": ORS_API_KEY}
        params = {"text": endereco_destino, "size": 1}
        
        geocode_response = requests.get(geocode_url, headers=headers, params=params)
        geocode_data = geocode_response.json()
        
        if not geocode_data.get("features"):
            return {"erro": "Endereço de destino não encontrado"}
        
        destino_coords = geocode_data["features"][0]["geometry"]["coordinates"]
        destino_lng, destino_lat = destino_coords
        
        # Se a origem não foi fornecida, retorna apenas as coordenadas do destino
        if not lat_origem or not lng_origem:
            map_url = f"https://www.openstreetmap.org/?mlat={destino_lat}&mlon={destino_lng}#map=15/{destino_lat}/{destino_lng}"
            return {
                "destino": {
                    "lat": destino_lat,
                    "lng": destino_lng,
                    "endereco": geocode_data["features"][0]["properties"].get("label", endereco_destino)
                },
                "map_url": map_url,
                "mensagem": "Apenas destino encontrado. Compartilhe sua localização para obter a rota completa."
            }
        
        # 2. Calcular a rota
        directions_url = "https://api.openrouteservice.org/v2/directions/driving-car"
        coordinates = [[lng_origem, lat_origem], [destino_lng, destino_lat]]
        
        directions_params = {
            "coordinates": coordinates,
            "instructions": True,
            "format": "json"
        }
        
        directions_response = requests.post(
            directions_url, 
            json=directions_params,
            headers=headers
        )
        
        route_data = directions_response.json()
        
        if "routes" not in route_data:
            return {"erro": "Não foi possível calcular a rota"}
        
        route = route_data["routes"][0]
        distance_km = round(route["summary"]["distance"] / 1000, 2)
        duration_min = round(route["summary"]["duration"] / 60, 0)
        
        # Gerar URL para visualização no mapa
        map_url = f"https://openrouteservice.org/directions?n1={lat_origem}&n2={lng_origem}&n3={destino_lat}&n4={destino_lng}&via=&pref=driving-car"
        
        return {
            "origem": {
                "lat": lat_origem,
                "lng": lng_origem
            },
            "destino": {
                "lat": destino_lat,
                "lng": destino_lng,
                "endereco": geocode_data["features"][0]["properties"].get("label", endereco_destino)
            },
            "distancia_km": distance_km,
            "duracao_min": duration_min,
            "map_url": map_url
        }
        
    except Exception as e:
        logger.exception(f"Erro ao calcular rota: {e}")
        return {"erro": f"Erro ao calcular rota: {str(e)}"}