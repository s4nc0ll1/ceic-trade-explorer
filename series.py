import pandas as pd
from datetime import date

class TradeDataManager:
    def __init__(self, ceic_client):
        self.ceic_client = ceic_client
        self.UN_COMTRADE_SOURCE_ID = "15371467" 

    def search_trade_data(self, reporter_id, reporter_name, flow, partner_country=None, hs_code=None, product_desc=None):
        """
        Busca metadatos de series (Snapshot).
        Ahora acepta product_desc para buscar por nombre (ej. "Maize", "Steel").
        """
        
        # 1. Construcción de Keywords
        # Estructura: "Flow" + "Description" + "Partner"
        search_terms = [f'"{flow}"']
        
        # Si hay descripción de producto, la agregamos
        if product_desc:
            search_terms.append(f'"{product_desc}"')
            
        if partner_country and partner_country.lower() not in ["world", "all", ""]:
            search_terms.append(f'"{partner_country}"')
        
        keyword_query = " ".join(search_terms)

        params = {
            "keyword": keyword_query,
            "geo": [reporter_id], 
            "source": [self.UN_COMTRADE_SOURCE_ID],
            "status": ["T"], 
            "limit": 100
        }

        try:
            results = self.ceic_client.search(**params)
            data_rows = []
            
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
                        
                        # Filtro estricto por HS Code si el usuario lo ingresó
                        if hs_code and str(hs_code).strip() != extracted_hs:
                            continue

                        # Inferencia simple de Partner (para display)
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
                            "Reporter": reporter_name,
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

    def get_series_history(self, series_ids, start_date):
        """
        Obtiene la historia (time points) para una lista de IDs.
        Fundamental para el workflow del 'Economista' (Trend Analysis).
        """
        try:
            # Convertir fecha a string YYYY-MM-DD si es objeto date
            s_date = start_date.strftime('%Y-%m-%d') if isinstance(start_date, date) else start_date
            
            # Llamada a la API para obtener datos históricos
            result = self.ceic_client.series(series_id=series_ids, start_date=s_date)
            
            all_series_data = []
            
            for series in result.data:
                meta = series.metadata
                # Procesar time points
                for tp in series.time_points:
                    all_series_data.append({
                        "Date": tp.date,
                        "Value": tp.value,
                        "Series Name": meta.name,
                        "Series ID": meta.id
                    })
            
            df = pd.DataFrame(all_series_data)
            if not df.empty:
                df['Date'] = pd.to_datetime(df['Date'])
                df = df.sort_values('Date')
            
            return df
            
        except Exception as e:
            print(f"Error fetching history: {e}")
            return pd.DataFrame()