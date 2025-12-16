import pandas as pd
from datetime import date

class TradeDataManager:
    def __init__(self, ceic_client):
        self.ceic_client = ceic_client
        self.UN_COMTRADE_SOURCE_ID = "15371467" 

    def search_trade_data(self, reporter_id, reporter_name, flow, partner_country=None, hs_code=None, product_desc=None):
        """
        Busca series, extrae el Partner real del nombre y filtra los falsos positivos.
        """
        
        # 1. Construcción de Keywords
        # Buscamos "Flow" + "Description" (+ "Partner" si existe)
        search_terms = [f'"{flow}"']
        
        if product_desc:
            search_terms.append(f'"{product_desc}"')
            
        # Normalizamos el partner buscado para comparaciones
        target_partner = None
        if partner_country and partner_country.lower() not in ["world", "all", ""]:
            target_partner = partner_country
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
                        
                        # --- A. EXTRACCIÓN HS CODE ---
                        trade_code_raw = getattr(meta, 'trade_code', getattr(meta, 'tradeCode', ''))
                        extracted_hs = ""
                        if trade_code_raw:
                            parts = trade_code_raw.split('|')
                            extracted_hs = parts[-1].strip() if len(parts) > 1 else trade_code_raw
                        
                        # Filtro estricto por HS Code
                        if hs_code and str(hs_code).strip() != extracted_hs:
                            continue

                        # --- B. PARSING DE NOMBRES (Extracción Real) ---
                        name_parts = [p.strip() for p in meta.name.split(':')]
                        
                        inferred_partner = "Unknown"
                        clean_description = meta.name 

                        # CASO HS6: Formato "DE: Exports: Brazil: X-Ray Tubes"
                        # Estructura: [ISO, Flow, Partner, Description...]
                        if len(extracted_hs) == 6:
                            if len(name_parts) >= 4:
                                inferred_partner = name_parts[2]
                                clean_description = ": ".join(name_parts[3:])
                            else:
                                # Fallback por si la estructura es rara
                                inferred_partner = "World" 
                                clean_description = name_parts[-1]

                        # CASO HS2 / HS4: Formato "Exports: Brazil: Cereals"
                        # Estructura: [Flow, Partner, Description...]
                        else:
                            if len(name_parts) >= 3:
                                inferred_partner = name_parts[1]
                                clean_description = ": ".join(name_parts[2:])
                            elif len(name_parts) == 2:
                                inferred_partner = name_parts[1]
                                clean_description = "Total" # Asunción común
                            else:
                                inferred_partner = "World"
                                clean_description = name_parts[-1]

                        # --- C. VALIDACIÓN DE PARTNER (Anti-Falsos Positivos) ---
                        # Si el usuario buscó "Brazil", pero el partner extraído dice "World" 
                        # (aunque la descripción diga "Brazil Nuts"), DESCARTAMOS la fila.
                        
                        if target_partner:
                            # Normalización simple para comparar (minúsculas)
                            p_inferred = inferred_partner.lower()
                            p_target = target_partner.lower()
                            
                            # Si el partner inferido NO contiene lo que buscamos, lo saltamos.
                            # Ej: Busco "Brazil". Inferred "World". -> Skip.
                            # Ej: Busco "China". Inferred "China". -> Keep.
                            if p_target not in p_inferred:
                                continue

                        # --- D. ARMADO DE FILA ---
                        row = {
                            "Series ID": meta.id,
                            "Period": str(getattr(meta, 'last_update_time', 'N/A'))[:10], 
                            "Flow": flow,
                            "Reporter": reporter_name,
                            "Partner": inferred_partner,     # Usamos el REAL extraído del nombre
                            "Cmdty Code": extracted_hs,
                            "Cmdty Desc": clean_description, # Descripción limpia
                            "Trade Value": getattr(meta, 'last_value', 0), 
                            "Unit": getattr(meta.unit, 'name', 'N/A')
                        }
                        data_rows.append(row)
            
            # --- CORRECCIÓN DE DUPLICADOS ---
            df = pd.DataFrame(data_rows)
            
            if not df.empty:
                # Eliminamos filas donde el 'Series ID' sea idéntico
                df = df.drop_duplicates(subset=["Series ID"])
            
            return df

        except Exception as e:
            print(f"ERROR en search_trade_data: {e}")
            return pd.DataFrame()

    def get_series_history(self, series_ids, start_date, end_date=None):
        """
        Obtiene la historia para una lista de IDs en un rango específico.
        """
        try:
            # Formateo de fechas a string YYYY-MM-DD
            s_date = start_date.strftime('%Y-%m-%d') if isinstance(start_date, date) else start_date
            
            # Preparamos kwargs para la llamada
            api_args = {
                "series_id": series_ids,
                "start_date": s_date
            }
            
            # Solo agregamos end_date si existe
            if end_date:
                e_date = end_date.strftime('%Y-%m-%d') if isinstance(end_date, date) else end_date
                api_args["end_date"] = e_date

            # Llamada a la API con los argumentos dinámicos
            result = self.ceic_client.series(**api_args)
            
            all_series_data = []
            
            for series in result.data:
                meta = series.metadata
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