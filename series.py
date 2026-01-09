import pandas as pd
import plotly.express as px
from datetime import date

#CEIC Colors
TEALISH = "#00A88F"
LAVENDER = "#F2CEEF"
DEEP_PURPLE = "#792D82"
DARK_BLUE = "#2F4858"

class TradeDataManager:
    def __init__(self, ceic_client):
        self.ceic_client = ceic_client
        self.UN_COMTRADE_SOURCE_ID = "15371467" 

    def _execute_search_query(self, reporter_id, flow, partner_country, hs_text_filter, product_desc):
        """
        Internal method: Constructs keywords and calls the CEIC API.
        """
        search_terms = [f'"{flow}"']
        
        #Send description text to API
        if hs_text_filter:
            search_terms.append(f'"{hs_text_filter}"')

        if product_desc:
            search_terms.append(f'"{product_desc}"')
            
        # Add partner to API query if specific
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
            return self.ceic_client.search(**params)
        except Exception as e:
            print(f"ERROR in API Call: {e}")
            return None

    def _process_search_results(self, results, flow, reporter_name, hs_code, partner_country):
        """
        Internal method: Filters, parses names, and builds the DataFrame.
        """
        data_rows = []
        
        # Prepare target partner for local filtering
        target_partner = None
        if partner_country and partner_country.lower() not in ["world", "all", ""]:
            target_partner = partner_country

        try:
            for result_page in results:
                if hasattr(result_page, 'data') and hasattr(result_page.data, 'items'):
                    for item in result_page.data.items:
                        meta = item.metadata
                        
                        # --- 1. HS Code Filtering ---
                        trade_code_raw = getattr(meta, 'trade_code', getattr(meta, 'tradeCode', ''))
                        extracted_hs = ""
                        if trade_code_raw:
                            parts = trade_code_raw.split('|')
                            extracted_hs = parts[-1].strip() if len(parts) > 1 else trade_code_raw
                        
                        # Strict Filter
                        if hs_code and str(hs_code).strip() != extracted_hs:
                            continue

                        # --- 2. Name Parsing ---
                        name_parts = [p.strip() for p in meta.name.split(':')]
                        inferred_partner = "Unknown"
                        clean_description = meta.name 

                        if len(extracted_hs) == 6:
                            if len(name_parts) >= 4:
                                inferred_partner = name_parts[2]
                                clean_description = ": ".join(name_parts[3:])
                            else:
                                inferred_partner = "World" 
                                clean_description = name_parts[-1]
                        else:
                            if len(name_parts) >= 3:
                                inferred_partner = name_parts[1]
                                clean_description = ": ".join(name_parts[2:])
                            elif len(name_parts) == 2:
                                inferred_partner = name_parts[1]
                                clean_description = "Total" 
                            else:
                                inferred_partner = "World"
                                clean_description = name_parts[-1]

                        # --- 3. Partner Validation ---
                        if target_partner:
                            p_inferred = inferred_partner.lower()
                            p_target = target_partner.lower()
                            if p_target not in p_inferred:
                                continue

                        # --- 4. Row Construction ---
                        row = {
                            "Series ID": meta.id,
                            "Period": str(getattr(meta, 'last_update_time', 'N/A'))[:10], 
                            "Flow": flow,
                            "Reporter": reporter_name,
                            "Partner": inferred_partner,
                            "Cmdty Code": extracted_hs,
                            "Cmdty Desc": clean_description,
                            "Trade Value": getattr(meta, 'last_value', 0), 
                            "Unit": getattr(meta.unit, 'name', 'N/A')
                        }
                        data_rows.append(row)
            
            df = pd.DataFrame(data_rows)
            if not df.empty:
                df = df.drop_duplicates(subset=["Series ID"])
            return df

        except Exception as e:
            print(f"ERROR in Data Processing: {e}")
            return pd.DataFrame()

    def search_trade_data(self, reporter_id, reporter_name, flow, partner_country=None, hs_code=None, hs_text_filter=None, product_desc=None):
        """
        Orchestrator function: Calls API then processes results.
        """
        results = self._execute_search_query(reporter_id, flow, partner_country, hs_text_filter, product_desc)
        
        if not results:
            return pd.DataFrame()

        return self._process_search_results(results, flow, reporter_name, hs_code, partner_country)

    def _fetch_history_from_api(self, series_ids, start_date, end_date):
        """
        Internal method: Handles date formatting and executes the API call.
        """
        try:
            # Date formatting
            s_date = start_date.strftime('%Y-%m-%d') if isinstance(start_date, date) else start_date
            
            api_args = {
                "series_id": series_ids,
                "start_date": s_date
            }
            
            if end_date:
                e_date = end_date.strftime('%Y-%m-%d') if isinstance(end_date, date) else end_date
                api_args["end_date"] = e_date

            return self.ceic_client.series(**api_args)
            
        except Exception as e:
            print(f"ERROR in API Call (History): {e}")
            return None

    def _process_history_data(self, api_result):
        """
        Internal method: Flattens the nested JSON response into a DataFrame.
        """
        if not api_result or not hasattr(api_result, 'data'):
            return pd.DataFrame()

        all_series_data = []
        
        try:
            for series in api_result.data:
                meta = series.metadata

                if hasattr(series, 'time_points'):
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
            print(f"ERROR in Data Processing (History): {e}")
            return pd.DataFrame()

    def get_series_history(self, series_ids, start_date, end_date=None):
        """
        Orchestrator function: Fetches history and returns a clean DataFrame.
        """
        # 1. Fetch
        result = self._fetch_history_from_api(series_ids, start_date, end_date)
        
        # 2. Process
        return self._process_history_data(result)
    
    def plot_history(self, df):
        if df.empty:
            return None
            
        fig = px.line(
            df, 
            x="Date", 
            y="Value", 
            color="Series Name", 
            markers=True,
            color_discrete_sequence=[TEALISH, DEEP_PURPLE, DARK_BLUE, "#FF6B6B"] 
        )
        
        fig.update_layout(
            title="Historical Trade Trends",
            xaxis_title="Date", 
            yaxis_title="Trade Value",
            plot_bgcolor="white",
            paper_bgcolor="white",
            font=dict(color="#333"),
            hovermode="x unified"
        )
        fig.update_xaxes(showgrid=True, gridcolor="#eee")
        fig.update_yaxes(showgrid=True, gridcolor="#eee")
        
        return fig