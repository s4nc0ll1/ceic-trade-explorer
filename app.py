import streamlit as st
import pandas as pd
from ceic_api_client.pyceic import Ceic
from series import TradeDataManager
import os
import json
from datetime import date, timedelta
import plotly.express as px

#Page config
st.set_page_config(page_title="CEIC Trade Data Explorer", layout="wide")

#CSS Styling
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

#Helper functions
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

def login_page():
    _, _, lang_col1, lang_col2 = st.columns([0.7, 0.1, 0.1, 0.1]) 
    with lang_col1: st.button("EN", key="lang_en", disabled=True) 
    with lang_col2: st.button("中文", key="lang_cn")

    col1, col2, col3 = st.columns([2, 1, 2])
    with col2: st.image("https://www.ceicdata.com/sites/default/files/logo_0.png", width=250)

    col1, col2, col3 = st.columns([2.5, 3.5, 2])
    with col2:
        st.title("Trade Data Explorer")
        st.markdown("Access detailed global trade data powered by **CEIC**.")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login", use_container_width=True)
            if submitted:
                try:
                    with st.spinner("Authenticating..."):
                        Ceic.login(username, password)
                        st.session_state.logged_in = True
                        st.rerun()
                except Exception as e:
                    st.error(f"Login failed: {e}")

def main_app():
    #Header
    top_left, top_mid, top_right = st.columns([1.5, 5.5, 1])
    with top_left:
        st.image("https://www.ceicdata.com/sites/default/files/logo_0.png", width=150)
        if st.button("Logout", key="logout_btn"):
            st.session_state.logged_in = False
            st.session_state.search_results = None
            st.rerun()
            
    with top_right:
        l1, l2 = st.columns(2)
        with l1: st.button("EN", key="main_lang_en", use_container_width=True)
        with l2: st.button("中文", key="main_lang_cn", use_container_width=True)

    st.title("Global Trade Data Search")
    st.markdown("Access detailed global trade data powered by **CEIC**.")
    st.markdown("---")

    #Data Loading
    geo_options = load_geo_options()
    reporter_list = list(geo_options.keys()) if geo_options else ["Argentina", "Brazil", "China", "United States"]
    partner_list = ["World"] + reporter_list
    hs_options = load_hs_codes()

    #Search Configuration
    with st.expander("Search Configuration", expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        
        with c1:
            selected_country_name = st.selectbox("Reporter (From)", options=reporter_list)
            selected_country_id = geo_options.get(selected_country_name) if geo_options else None
            
        with c2:
            flow = st.selectbox("Trade Flow", ["Exports", "Imports"])
            
        with c3:
            product_desc = st.text_input("Product Description", placeholder="e.g. Soya, Cars")
            
        with c4:
            selected_hs_label = st.selectbox(
                "HS Commodity", 
                options=["All Commodities"] + list(hs_options.keys()),
                index=0
            )
            
            hs_code = None
            hs_text_filter = None
            
            if selected_hs_label != "All Commodities":
                hs_code = hs_options[selected_hs_label]
                if " - " in selected_hs_label:
                    hs_text_filter = selected_hs_label.split(" - ", 1)[1]

        c5, c6 = st.columns([1, 3])
        with c5:
            partner = st.selectbox("Partner (To)", options=partner_list, index=0)
        with c6:
            d1, d2 = st.columns(2)
            with d1: start_date = st.date_input("Start Date", value=date.today() - timedelta(days=365*3))
            with d2: end_date = st.date_input("End Date", value=date.today())

        st.markdown("<br>", unsafe_allow_html=True)
        search_btn = st.button("Search Data", type="primary", use_container_width=True)

    # Search Logic
    if search_btn:
        manager = TradeDataManager(Ceic)
        with st.spinner(f"Searching {flow} from {selected_country_name}..."):
            
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

            st.info(f"**Found {len(df_results)} series.** Select rows to visualize history.")

            event = st.dataframe(
                df_results,
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="multi-row",
                column_config={
                    "Trade Value": st.column_config.NumberColumn(format="$%d"),
                    "Series ID": st.column_config.TextColumn(help="Unique ID"),
                }
            )
            
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
                    tab1, tab2 = st.tabs(["Chart", "Data"])
                    with tab1:
                        fig = manager.plot_history(df_history)
                        st.plotly_chart(fig, use_container_width=True)
                    with tab2:
                        st.dataframe(df_history, use_container_width=True)
                else:
                    st.warning("No history found.")
            
            csv = df_results.to_csv(index=False).encode('utf-8')
            st.download_button("Download CSV", csv, f"trade_{selected_country_name}.csv", "text/csv")
        else:
            st.warning("No results found. Try adjusting filters.")

if __name__ == '__main__':
    initialize_session_state()
    if st.session_state.logged_in:
        main_app()
    else:
        login_page()