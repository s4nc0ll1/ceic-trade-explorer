import streamlit as st
import pandas as pd
from ceic_api_client.pyceic import Ceic
from series import TradeDataManager
import os
import json
from datetime import date, timedelta
import plotly.express as px # Asegúrate de importar esto si usas gráficas

# Configuración de página
st.set_page_config(page_title="CEIC Trade Data Explorer", layout="wide")

# --- FUNCIÓN PARA CARGAR JSON ---
@st.cache_data
def load_geo_options():
    """Carga los países desde filters/geo_data.json"""
    json_path = os.path.join("filters", "geo_data.json")
    
    if not os.path.exists(json_path):
        # Fallback silencioso para no romper la UI si falta el archivo
        return {}

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        countries = [item for item in data if item.get("type") == "COUNTRY"]
        countries_sorted = sorted(countries, key=lambda x: x['title'])
        
        return {item['title']: item['id'] for item in countries_sorted}
    except Exception as e:
        st.error(f"Error leyendo el JSON: {e}")
        return {}

def initialize_session_state():
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    # ELIMINADO: if 'ceic_client' ... (Ya no lo necesitamos aquí)
    if 'search_results' not in st.session_state:
        st.session_state.search_results = None

def login_page():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image("https://www.ceicdata.com/sites/default/files/logo_0.png", width=200)
        st.title("Trade Data Explorer")
        st.markdown("Access detailed global trade data powered by **CEIC**.")
        
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login")
            
            if submitted:
                if not username or not password:
                    st.warning("Please enter both username and password.")
                else:
                    try:
                        with st.spinner("Authenticating..."):
                            # 1. Login normal
                            Ceic.login(username, password)
                            
                            # 2. Solo marcamos que está logueado. 
                            # NO guardamos el objeto Ceic en session_state para evitar que se cuelgue.
                            st.session_state.logged_in = True
                            st.rerun()
                    except Exception as e:
                        st.error(f"Login failed: {e}")

def main_app():
    # Sidebar
    with st.sidebar:
        st.image("https://www.ceicdata.com/sites/default/files/logo_0.png", width=150)
        if st.button("Logout"):
            st.session_state.logged_in = False
            st.session_state.search_results = None
            st.rerun()

    st.title("Global Trade Data Search")
    st.markdown("---")

    # --- CARGA DE DATOS ---
    geo_options = load_geo_options()

    reporter_list = list(geo_options.keys()) if geo_options else ["Argentina", "Brazil", "China", "United States"]
    partner_list = ["World"] + reporter_list

    # --- SECCIÓN DE FILTROS ---
    with st.expander("Search Configuration", expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        
        with c1:
            selected_country_name = st.selectbox("Reporter (From)", options=reporter_list)
            selected_country_id = geo_options.get(selected_country_name) if geo_options else None
            
        with c2:
            flow = st.selectbox("Trade Flow", ["Exports", "Imports"])
            
        with c3:
            # Nuevo campo de descripción (Workflow Strategist)
            product_desc = st.text_input("Product Description", placeholder="e.g. Soya, Cars")
            
        with c4:
            hs_code = st.text_input("HS Code (Optional)", placeholder="e.g. 10, 0303")
            
        c5, c6 = st.columns([1, 3])
        with c5:
            partner = st.selectbox("Partner (To)", options=partner_list, index=0)
        with c6:
            d1, d2 = st.columns(2)
            with d1:
                start_date = st.date_input("Start Date", value=date.today() - timedelta(days=365*3))
            with d2:
                end_date = st.date_input("End Date", value=date.today())

        search_btn = st.button("Search Data", type="primary")

    # --- LÓGICA DE BÚSQUEDA ---
    if search_btn:
        # Aquí pasamos la clase Ceic importada directamente.
        # Python ya sabe que está logueada porque el proceso sigue vivo.
        manager = TradeDataManager(Ceic)
        
        with st.spinner(f"Searching {flow} from {selected_country_name}..."):
            
            df = manager.search_trade_data(
                reporter_id=selected_country_id,
                reporter_name=selected_country_name, 
                flow=flow,
                partner_country=partner,
                hs_code=hs_code,
                product_desc=product_desc
            )
            st.session_state.search_results = df

    # --- VISUALIZACIÓN DE RESULTADOS ---
    if st.session_state.search_results is not None:
        df_results = st.session_state.search_results
        
        if not df_results.empty:
            st.success(f"**Found {len(df_results)} series.** Select rows to visualize history.")
            
            # Tabla interactiva
            event = st.dataframe(
                df_results,
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="multi-row",
                column_config={
                    "Trade Value": st.column_config.NumberColumn(
                        "Trade Value",
                        format="$%d",  # Formato moneda sin decimales
                        help="Last available value in USD"
                    ),
                    "Series ID": st.column_config.TextColumn(help="Unique ID"),
                    "Period": st.column_config.TextColumn(width="small"),
                    "HS Code": st.column_config.TextColumn(width="small")
                }
            )
            
            # --- Lógica de Gráficos (Drill Down) ---
            if event.selection.rows:
                selected_indices = event.selection.rows
                selected_series_ids = df_results.iloc[selected_indices]["Series ID"].tolist()
                
                st.divider()
                st.subheader("Historical Trends")
                
                manager = TradeDataManager(Ceic)
                with st.spinner("Fetching history..."):
                    df_history = manager.get_series_history(
                        series_ids=selected_series_ids, 
                        start_date=start_date,
                        end_date=end_date
                    )
                
                if not df_history.empty:
                    fig = px.line(df_history, x="Date", y="Value", color="Series Name", markers=True)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.warning("No history found for selected items.")
            
            # Botón de descarga CSV de la tabla
            csv = df_results.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Download Table CSV",
                data=csv,
                file_name=f"trade_data_{selected_country_name}.csv",
                mime="text/csv",
            )
        else:
            st.warning("No results found.")

if __name__ == '__main__':
    initialize_session_state()
    if st.session_state.logged_in:
        main_app()
    else:
        login_page()