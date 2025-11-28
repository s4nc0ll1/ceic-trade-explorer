import streamlit as st
import pandas as pd
from ceic_api_client.pyceic import Ceic
from series import TradeDataManager
import os
import json

# Configuración de página
st.set_page_config(page_title="CEIC Trade Data Explorer", layout="wide")

# --- NUEVA FUNCIÓN PARA CARGAR JSON ---
@st.cache_data
def load_geo_options():
    """Carga los países desde filters/geo_data.json"""
    json_path = os.path.join("filters", "geo_data.json")
    
    if not os.path.exists(json_path):
        st.error(f"Error: No se encontró el archivo {json_path}")
        return {}

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # Filtramos solo los que son tipo 'COUNTRY' y creamos un diccionario {Nombre: ID}
        # Ordenamos alfabéticamente por nombre
        countries = [item for item in data if item.get("type") == "COUNTRY"]
        countries_sorted = sorted(countries, key=lambda x: x['title'])
        
        return {item['title']: item['id'] for item in countries_sorted}
    except Exception as e:
        st.error(f"Error leyendo el JSON: {e}")
        return {}

def initialize_session_state():
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'ceic_client' not in st.session_state:
        st.session_state.ceic_client = None

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
                            Ceic.login(username, password)
                            st.session_state.ceic_client = Ceic
                            st.session_state.logged_in = True
                            st.rerun()
                    except Exception as e:
                        st.error(f"Login failed: {e}")

def main_app():
    col_title, col_logout = st.columns([6, 1])
    with col_title:
        st.title("Global Trade Data Search")
    with col_logout:
        if st.button("Logout"):
            st.session_state.logged_in = False
            st.session_state.ceic_client = None
            st.rerun()

    st.markdown("---")

    # --- CARGA DE DATOS ---
    geo_options = load_geo_options() # Diccionario {'China': '0', 'Albania': '2865', ...}

    # --- SECCIÓN DE FILTROS ---
    with st.container():
        st.subheader("Refine your search")
        
        c1, c2, c3, c4 = st.columns(4)
        
        with c1:
            # Dropdown usando las llaves del diccionario (Nombres)
            selected_country_name = st.selectbox("Reporter (From)", options=list(geo_options.keys()))
            # Obtenemos el ID correspondiente para mandar a la API
            selected_country_id = geo_options.get(selected_country_name)
            
        with c2:
            flow = st.selectbox("Trade Flow", ["Exports", "Imports"])
            
        with c3:
            hs_code = st.text_input("HS Commodity Code", placeholder="e.g. 10, 0303", help="Leave empty for Total")
            
        with c4:
            partner = st.text_input("Partner (To)", placeholder="e.g. Brazil, World", value="World")

    st.markdown("<br>", unsafe_allow_html=True)
    search_btn = st.button("Search Data", type="primary", use_container_width=True)

    # --- LÓGICA ---
    if search_btn:
        if not st.session_state.ceic_client:
            st.error("Client session lost. Please relogin.")
            return

        manager = TradeDataManager(st.session_state.ceic_client)
        
        with st.spinner(f"Searching {flow} from {selected_country_name} (ID: {selected_country_id})..."):
            
            # Pasamos ID y Nombre. El ID para filtrar, el Nombre para llenar la tabla.
            df_results = manager.search_trade_data(
                reporter_id=selected_country_id,
                reporter_name=selected_country_name, 
                flow=flow,
                partner_country=partner,
                hs_code=hs_code
            )
        
        st.markdown("---")
        
        if not df_results.empty:
            st.success(f"**Found {len(df_results)} series matching your criteria.**")
            
            st.dataframe(
                df_results,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Trade Value": st.column_config.NumberColumn(
                        "Trade Value (Last)",
                        format="%.2f",
                    )
                }
            )
            
            csv = df_results.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Download Results as CSV",
                data=csv,
                file_name=f"trade_data_{selected_country_name}_{flow}.csv",
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