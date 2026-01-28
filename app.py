# --- START OF FILE app.py ---

import streamlit as st
import pandas as pd
from ceic_api_client.pyceic import Ceic
from series import TradeDataManager
import os
import json
from datetime import date, timedelta
import plotly.express as px
from translations import TRANSLATIONS # Import the translations

# --- HELPER FOR TRANSLATION ---
def get_translation(key):
    """Retrieves the translation for the given key based on session state."""
    lang = st.session_state.get('language', "EN")
    # 1. Get dictionary for specific language (default to EN)
    # 2. Get key from that dictionary (default to key itself if missing)
    return TRANSLATIONS.get(lang, {}).get(key, key)

# Page config
st.set_page_config(page_title="CEIC Trade Data Explorer", layout="wide")

# CSS Styling
st.markdown( 
    """
    <style>
    .stApp { background-color: #E6E6FA; min-height: 100vh; }
    .stApp > header { background-color: transparent; }
    .streamlit-expanderHeader { background-color: white; border-radius: 4px; }
    div[data-testid="stExpander"] { background-color: rgba(255, 255, 255, 0.5); border-radius: 4px; }
    div.stButton > button { border-radius: 4px; }
    </style>
    """,
    unsafe_allow_html=True
)

# Helper functions
@st.cache_data
def load_hs_codes():
    json_path = os.path.join("filters", "hs_codes.json")
    if not os.path.exists(json_path): return {}
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Returns dict: "0902 - Tea" -> "0902"
    return {f"{item['code']} - {item['description']}": item['code'] for item in data}

def load_geo_options():
    json_path = os.path.join("filters", "geo_data.json")
    if not os.path.exists(json_path): return {}
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        countries = [item for item in data if item.get("type") == "COUNTRY"]
        countries_sorted = sorted(countries, key=lambda x: x['title'])
        return {item['title']: item['id'] for item in countries_sorted}
    except Exception as e:
        st.error(f"Error reading JSON: {e}")
        return {}

def initialize_session_state():
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'search_results' not in st.session_state:
        st.session_state.search_results = None
    if 'language' not in st.session_state:
        st.session_state.language = "EN"

def login_page():
    _, _, lang_col1, lang_col2 = st.columns([0.7, 0.1, 0.1, 0.1]) 
    
    # Language Toggle Buttons
    with lang_col1: 
        if st.button("EN", key="lang_en", disabled=st.session_state.language == "EN"):
            st.session_state.language = "EN"
            st.rerun()
            
    with lang_col2: 
        if st.button("中文", key="lang_cn", disabled=st.session_state.language == "CN"):
            st.session_state.language = "CN"
            st.rerun()

    col1, col2, col3 = st.columns([2, 1, 2])
    with col2: st.image("https://www.ceicdata.com/sites/default/files/logo_0.png", width=250)

    col1, col2, col3 = st.columns([2.5, 3.5, 2])
    with col2:
        st.title(get_translation("CEIC Trade Data Explorer"))
        st.markdown(get_translation("Access detailed global trade data powered by **CEIC**."))

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            username = st.text_input(get_translation("Username"))
            password = st.text_input(get_translation("Password"), type="password")
            submitted = st.form_submit_button(get_translation("Login"), use_container_width=True)
            if submitted:
                try:
                    with st.spinner(get_translation("Authenticating...")):
                        Ceic.login(username, password)
                        st.session_state.logged_in = True
                        st.rerun()
                except Exception as e:
                    st.error(get_translation("Login failed: {}").format(e))

def main_app():
    # Header
    top_left, top_mid, top_right = st.columns([1.5, 5.5, 1])
    with top_left:
        st.image("https://www.ceicdata.com/sites/default/files/logo_0.png", width=150)
        if st.button(get_translation("Logout"), key="logout_btn"):
            st.session_state.logged_in = False
            st.session_state.search_results = None
            st.rerun()
            
    with top_right:
        l1, l2 = st.columns(2)
        with l1: 
            if st.button("EN", key="main_lang_en", use_container_width=True, disabled=st.session_state.language == "EN"):
                st.session_state.language = "EN"
                st.rerun()
        with l2: 
            if st.button("中文", key="main_lang_cn", use_container_width=True, disabled=st.session_state.language == "CN"):
                st.session_state.language = "CN"
                st.rerun()

    st.title(get_translation("Global Trade Data Search"))
    st.markdown(get_translation("Access detailed global trade data powered by **CEIC**."))
    st.markdown("---")

    # Data Loading
    geo_options = load_geo_options()
    # Note: We keep keys in English for API logic, but could map display names if needed.
    # For now, Country names usually stay in English or require a mapping file.
    reporter_list = list(geo_options.keys()) if geo_options else ["Argentina", "Brazil", "China", "United States"]
    partner_list = ["World"] + reporter_list
    hs_options = load_hs_codes()

    # Search Configuration
    with st.expander(get_translation("Search Configuration"), expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        
        with c1:
            selected_country_name = st.selectbox(get_translation("Reporter (From)"), options=reporter_list)
            selected_country_id = geo_options.get(selected_country_name) if geo_options else None
            
        with c2:
            flow = st.selectbox(get_translation("Trade Flow"), ["Exports", "Imports"])
            
        with c3:
            product_desc = st.text_input(get_translation("Product Description"), placeholder=get_translation("e.g. Soya, Cars"))
            
        with c4:
            selected_hs_label = st.selectbox(
                get_translation("HS Commodity"), 
                options=[get_translation("All Commodities")] + list(hs_options.keys()),
                index=0
            )
            
            hs_code = None
            hs_text_filter = None
            
            # Logic uses English "All Commodities" or Translated one?
            # Safe way: check if it matches the first option.
            if selected_hs_label != get_translation("All Commodities"):
                # We assume hs_options keys are "Code - Description"
                hs_code = hs_options.get(selected_hs_label)
                if " - " in selected_hs_label:
                    hs_text_filter = selected_hs_label.split(" - ", 1)[1]

        c5, c6 = st.columns([1, 3])
        with c5:
            partner = st.selectbox(get_translation("Partner (To)"), options=partner_list, index=0)
        with c6:
            d1, d2 = st.columns(2)
            with d1: start_date = st.date_input(get_translation("Start Date"), value=date.today() - timedelta(days=365*3))
            with d2: end_date = st.date_input(get_translation("End Date"), value=date.today())

        st.markdown("<br>", unsafe_allow_html=True)
        search_btn = st.button(get_translation("Search Data"), type="primary", use_container_width=True)

    # Search Logic
    if search_btn:
        manager = TradeDataManager(Ceic)
        # Translating the spinner text
        spinner_text = get_translation("Searching {} from {}...").format(flow, selected_country_name)
        
        with st.spinner(spinner_text):
            
            df = manager.search_trade_data(
                reporter_id=selected_country_id,
                reporter_name=selected_country_name, 
                flow=flow,
                partner_country=partner,
                hs_code=hs_code,
                hs_text_filter=hs_text_filter,
                product_desc=product_desc
            )
            st.session_state.search_results = df

    # Results
    if st.session_state.search_results is not None:
        df_results = st.session_state.search_results
        
        if not df_results.empty:
            
            # Translated Info Message
            msg = get_translation("**Found {} series.** Select rows to visualize history.").format(len(df_results))
            st.info(msg)

            # Translate Columns for Display
            # We create a copy or rename columns just for the dataframe view if we want full translation
            # For simplicity, we keep data columns as is, but translate header configs
            
            event = st.dataframe(
                df_results,
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="multi-row",
                column_config={
                    "Trade Value": st.column_config.NumberColumn(
                        label=get_translation("Trade Value"),
                        format="$%d"
                    ),
                    "Series ID": st.column_config.TextColumn(
                        label=get_translation("Series ID"),
                        help="Unique ID"
                    ),
                    "Period": st.column_config.TextColumn(label=get_translation("Period")),
                    "Flow": st.column_config.TextColumn(label=get_translation("Flow")),
                    "Reporter": st.column_config.TextColumn(label=get_translation("Reporter")),
                    "Partner": st.column_config.TextColumn(label=get_translation("Partner")),
                    "Cmdty Code": st.column_config.TextColumn(label=get_translation("Cmdty Code")),
                    "Cmdty Desc": st.column_config.TextColumn(label=get_translation("Cmdty Desc")),
                    "Unit": st.column_config.TextColumn(label=get_translation("Unit")),
                }
            )
            
            if event.selection.rows:
                selected_indices = event.selection.rows
                selected_series_ids = df_results.iloc[selected_indices]["Series ID"].tolist()
                
                st.divider()
                st.subheader(get_translation("Historical Trends"))
                
                manager = TradeDataManager(Ceic)
                with st.spinner(get_translation("Fetching history...")):
                    df_history = manager.get_series_history(
                        series_ids=selected_series_ids, 
                        start_date=start_date,
                        end_date=end_date
                    )
                
                if not df_history.empty:
                    tab1, tab2 = st.tabs([get_translation("Chart"), get_translation("Data")])
                    with tab1:
                        fig = manager.plot_history(df_history)
                        # We can update the title of the chart here to be translated
                        fig.update_layout(title=get_translation("Historical Trends"))
                        st.plotly_chart(fig, use_container_width=True)
                    with tab2:
                        st.dataframe(df_history, use_container_width=True)
                else:
                    st.warning(get_translation("No history found."))
            
            csv = df_results.to_csv(index=False).encode('utf-8')
            st.download_button(
                get_translation("Download CSV"), 
                csv, 
                f"trade_{selected_country_name}.csv", 
                "text/csv"
            )
        else:
            st.warning(get_translation("No results found. Try adjusting filters."))

if __name__ == '__main__':
    initialize_session_state()
    if st.session_state.logged_in:
        main_app()
    else:
        login_page()