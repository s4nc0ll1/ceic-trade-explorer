import pandas as pd
import re

class TradeDataManager:
    def __init__(self, ceic_client):
        self.ceic_client = ceic_client
        self.UN_COMTRADE_SOURCE_ID = "15371467" 

    def search_trade_data(self, reporter_id, reporter_name, flow, partner_country=None, hs_code=None):
        """
        Busca series usando el ID geográfico del reporter.
        
        Args:
            reporter_id (str): ID numérico del país (ej. "3060" para Argentina).
            reporter_name (str): Nombre del país (solo para display en la tabla).
            flow (str): "Exports" o "Imports".
            ...
        """
        
        # 1. Construcción de Keywords
        # Ya no necesitamos poner el nombre del país en el keyword porque usamos el filtro 'geo'
        search_terms = [f'"{flow}"']
        
        if partner_country and partner_country.lower() not in ["world", "all", ""]:
            search_terms.append(f'"{partner_country}"')
        
        keyword_query = " ".join(search_terms)

        # 2. Parámetros de búsqueda
        params = {
            "keyword": keyword_query,
            "geo": [reporter_id], # <--- CAMBIO IMPORTANTE: Filtro por ID
            "source": [self.UN_COMTRADE_SOURCE_ID],
            "status": ["T"], 
            "limit": 100
        }

        print(f"DEBUG: Buscando GEO ID: {reporter_id} | Keyword: {keyword_query}")

        try:
            results = self.ceic_client.search(**params)
            data_rows = []
            
            # 3. Procesamiento (Igual que antes, pero usando snake_case seguro)
            for result_page in results:
                if hasattr(result_page, 'data') and hasattr(result_page.data, 'items'):
                    for item in result_page.data.items:
                        meta = item.metadata
                        
                        # Extraer HS Code
                        trade_code_raw = getattr(meta, 'trade_code', getattr(meta, 'tradeCode', ''))
                        extracted_hs = ""
                        if trade_code_raw:
                            parts = trade_code_raw.split('|')
                            extracted_hs = parts[-1].strip() if len(parts) > 1 else trade_code_raw
                        
                        # Filtro HS Code
                        if hs_code and str(hs_code).strip() != extracted_hs:
                            continue

                        # Inferir Partner
                        name_parts = meta.name.split(':')
                        partner_inferred = "World"
                        if len(name_parts) > 2:
                            partner_candidate = name_parts[2].strip()
                            if not any(char.isdigit() for char in partner_candidate): 
                                partner_inferred = partner_candidate

                        row = {
                            "Series ID": meta.id,
                            "Period": str(getattr(meta, 'last_update_time', 'N/A'))[:10], 
                            "Flow": flow,
                            "Reporter": reporter_name, # Usamos el nombre pasado por argumento
                            "Partner": partner_inferred,
                            "Cmdty Code": extracted_hs,
                            "Cmdty Desc": meta.name,
                            "Trade Value": getattr(meta, 'last_value', 0), 
                            "Unit": getattr(meta.unit, 'name', 'N/A')
                        }
                        data_rows.append(row)
            
            return pd.DataFrame(data_rows)

        except Exception as e:
            print(f"ERROR en search_trade_data: {e}")
            return pd.DataFrame()