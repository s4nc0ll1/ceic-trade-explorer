import json
import os
import time
from ceic_api_client.pyceic import Ceic
import pandas as pd

# --- CONFIGURACIÓN ---
# Pon tus credenciales aquí temporalmente o asegúrate de que el script las pida
# Si ya tienes sesión guardada en caché por pyceic, a veces no es necesario login explícito
USERNAME = ""
PASSWORD = ""

# ID de UN Comtrade
SOURCE_ID = "15371467" 
# ID de "World" (Generalmente es '1' o similar en CEIC, pero usaremos búsqueda por texto para asegurar)
# En tu geo_data.json, busca el ID de "World". Si no lo tienes, el script buscará por keyword "World".

def extract_all_hs_codes():
    print("🚀 Iniciando extracción de HS Codes maestros...")
    
    # Intentar login
    try:
        Ceic.login(USERNAME, PASSWORD)
        print("✅ Login exitoso.")
    except Exception as e:
        print(f"⚠️ Aviso de Login: {e} (Si ya tienes sesión activa, ignora esto)")

    # 1. Búsqueda Amplia: "Exports" + "World"
    # Esto debería traer el total mundial de cada commodity
    params = {
        "keyword": '"Exports" "World"', 
        "source": [SOURCE_ID],
        "status": ["T"], 
        "limit": 100,
        "offset": 0
    }

    hs_dictionary = {} # Diccionario para evitar duplicados { "CODIGO": "DESCRIPCION" }
    
    max_pages = 100 # Seguridad: Máximo 10,000 items (hay aprox 5-6k códigos HS relevantes)
    page = 0
    
    while page < max_pages:
        print(f"🔄 Procesando página {page + 1} (Offset: {params['offset']})...")
        
        try:
            results = Ceic.search(**params)
            
            if not hasattr(results, 'data') or not hasattr(results.data, 'items') or not results.data.items:
                print("✅ Fin de resultados.")
                break
            
            items = results.data.items
            
            for item in items:
                meta = item.metadata
                
                # --- A. Extraer Código HS ---
                trade_code_raw = getattr(meta, 'trade_code', getattr(meta, 'tradeCode', ''))
                if not trade_code_raw:
                    continue
                    
                # Limpieza: "HS 2022 | 10" -> "10"
                parts_code = trade_code_raw.split('|')
                code = parts_code[-1].strip() if len(parts_code) > 1 else trade_code_raw
                
                # --- B. Extraer Descripción ---
                # Usamos la lógica que ya perfeccionamos en series.py
                name_parts = [p.strip() for p in meta.name.split(':')]
                
                # Formato esperado: "Exports: World: Cereals"
                # Tomamos la última parte que suele ser la descripción
                description = name_parts[-1]
                
                # Limpieza extra: A veces dice "Cereals; wheat" -> queremos el texto limpio
                # Si la descripción es "Total", la guardamos como tal para el código vacio o TOTAL
                
                # Guardamos en el diccionario (la clave es el código, así evitamos repeticiones)
                if code not in hs_dictionary:
                    hs_dictionary[code] = description
            
            # Control de Paginación
            if len(items) < params['limit']:
                print("✅ Última página alcanzada.")
                break
                
            params['offset'] += params['limit']
            page += 1
            time.sleep(0.2) # Respetar API rate limits
            
        except Exception as e:
            print(f"❌ Error en paginación: {e}")
            break

    # --- GUARDAR RESULTADOS ---
    if hs_dictionary:
        # Convertir a lista de objetos para el JSON
        output_list = [{"code": k, "description": v} for k, v in hs_dictionary.items()]
        
        # Ordenar por código numérico (truco para ordenar "1", "2", "10" correctamente)
        # Manejamos excepciones por si hay códigos alfanuméricos
        try:
            output_list.sort(key=lambda x: int(x['code']) if x['code'].isdigit() else 999999)
        except:
            output_list.sort(key=lambda x: x['code'])

        # Guardar archivo
        os.makedirs("filters", exist_ok=True)
        file_path = os.path.join("filters", "hs_codes.json")
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(output_list, f, indent=4, ensure_ascii=False)
            
        print(f"🎉 Éxito! Se guardaron {len(output_list)} códigos HS en '{file_path}'")
    else:
        print("⚠️ No se encontraron códigos.")

if __name__ == "__main__":
    extract_all_hs_codes()