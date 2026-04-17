import streamlit as st
import requests
import pandas as pd
import pydeck as pdk
import io

st.set_page_config(page_title="Geo-Anchor Miami", layout="wide")

# --- СТИЛИЗАЦИЯ ---
st.markdown("""
    <style>
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #eee; }
    [data-testid="stMetricValue"] { font-size: 32px !important; color: #1E3A8A; font-weight: bold; }
    .report-text { font-size: 16px; line-height: 1.5; }
    /* Кастомный стиль для тултипа pydeck */
    .deck-tooltip { font-family: Helvetica, Arial, sans-serif; padding: 10px !important; border-radius: 8px !important; box-shadow: 0 4px 6px rgba(0,0,0,0.1) !important;}
    </style>
    """, unsafe_allow_html=True)

def call_api(api_key, q):
    url = "https://geo-anchor.p.rapidapi.com/v1/anchor"
    headers = {
        "X-RapidAPI-Key": api_key.strip(), 
        "X-RapidAPI-Host": "geo-anchor.p.rapidapi.com",
        "Content-Type": "application/json"
    }
    
    # 1. Формируем элемент запроса
    q_str = str(q).replace(" ", "")
    if "," in q_str:
        try:
            parts = q_str.split(",")
            # Если ввели цифры с запятой — это координаты
            payload_item = {
                "lat": float(parts[0]),
                "lng": float(parts[1]),
                "address": "Manual Point Check"
            }
        except ValueError:
            payload_item = q # Если не цифры, то как текст
    else:
        payload_item = q # Обычный адрес

    # 2. Оборачиваем в список "addresses", как того требует API
    payload = {"addresses": [payload_item]}
            
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        return response.json(), payload
    except Exception as e:
        return {"status": "error", "message": f"Connection error: {str(e)}"}, payload

def extract_data(res):
    if isinstance(res, list) and len(res) > 0:
        res = res[0]
    if isinstance(res, dict):
        if "0" in res: return extract_data(res["0"])
        return res
    return {"status": "error", "message": "Unknown API Response Format"}

# --- SIDEBAR ---
with st.sidebar:
    st.title("🏙️ Geo-Anchor")
    user_api_key = st.text_input("RapidAPI Key", type="password")
    st.markdown("---")
    st.markdown("### Contact")
    st.markdown("**Ivan Fursov**")
    st.caption("Analytics Engineer")
    
    # Лаконичные ссылки
    st.markdown("""
        <div style="line-height: 2;">
            <a href="https://t.me/fursovi3" style="text-decoration:none;">✈️ Telegram</a><br>
            <a href="https://www.linkedin.com/in/ivan-fursov-86ba793a8/" style="text-decoration:none;">💼 LinkedIn</a><br>
            <span style="font-size: 14px;">✉️ ivanedgery@gmail.com </span>
        </div>
    """, unsafe_allow_html=True)
    st.caption("Data updated in March 2026.")
    st.caption("For information purposes only. Always verify with the Miami Zoning Department before making financial decisions.")

# st.title("Miami Property Intelligence")

# ==========================================
# BATCH PROCESSING
# ==========================================
with st.expander("📂 Batch Processing", expanded=False):
    st.markdown("Upload a Excel file. Ensure it has a column named **'address'** or **'location'**.")
    
    # 1. Загрузка файла
    uploaded_file = st.file_uploader("Choose a file", type=['csv', 'xlsx'])
    
    if uploaded_file:
        # Читаем файл в зависимости от расширения
        if uploaded_file.name.endswith('.csv'):
            df_input = pd.read_csv(uploaded_file)
        else:
            df_input = pd.read_excel(uploaded_file)
            
        # Автоматический поиск колонки с адресом
        col_name = next((c for c in df_input.columns if c.lower() in ['address', 'query', 'location', 'input']), None)
        
        if not col_name:
            st.error("Column with addresses not found! Please rename your column to 'address'.")
        else:
            st.success(f"Found address column: **'{col_name}'**")
            
            if st.button("🚀 Process Batch", type="primary"):
                results_list = []
                map_points = []
                
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                for i, row in df_input.iterrows():
                    val = str(row[col_name]).strip()
                    status_text.text(f"Processing {i+1}/{len(df_input)}: {val[:30]}...")
                    
                    # Вызов твоего API
                    raw_res, _ = call_api(user_api_key, val)
                    data = extract_data(raw_res)
                    
                    row_res = {"input_query": val, "status": data.get('status')}
                    
                    if data.get('status') == 'success':
                        p = data.get('parcel') or {}
                        z = p.get('zoning') or {}
                        m = data.get('match_metadata') or {}
                        l = data.get('location') or {}
                        
                        row_res.update({
                            "folio_id": str(p.get('id') or "N/A"),
                            "anchor_id": str(data.get('anchor_id') or "N/A"),
                            "zoning_code": str(z.get('code') or "N/A"),
                            "zoning_category": str(z.get('category') or "N/A"),
                            "zoning_description": str(z.get('description') or "N/A"),
                            "future_land_use": str(p.get('land_use') or "N/A"),
                            "max_height_stories": str(z.get('max_height_stories') or "N/A"),
                            "clean_address": str(m.get('clean_address') or "N/A"),
                            "input_address": str(m.get('input_address') or val), # Принудительно в строку
                            "latitude": l.get('lat'), # Числа можно оставлять как есть
                            "longitude": l.get('lng'),
                            "jurisdiction": str(z.get('jurisdiction') or "N/A"),                            
                            "confidence": str(m.get('confidence') or "N/A"),
                            "source": str(m.get('source') or "N/A")
                        })
                        
                        map_points.append({
                            "lat": l['lat'], 
                            "lng": l['lng'],
                            "tooltip_text": f"<b>{m.get('clean_address')}</b><br>Folio: {p.get('id')}"
                        })
                    else:
                        row_res["error_note"] = data.get('error_code') or data.get('message')
                    
                    results_list.append(row_res)
                    progress_bar.progress((i + 1) / len(df_input))
                
                progress_bar.empty()
                status_text.success(f"Batch completed: {len(results_list)} records processed.")

                # --- ВЫВОД РЕЗУЛЬТАТОВ ---
                df_results = pd.DataFrame(results_list)

                # Экспорт в Excel
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    df_results.to_excel(writer, index=False, sheet_name='Batch Analysis')
                
                st.download_button(
                    label="📥 Download Full Excel Report",
                    data=buffer.getvalue(),
                    file_name=f"batch_results_{len(df_results)}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

                # Таблица с исправленным параметром ширины
                st.write("### 📊 Results Preview")
                st.dataframe(df_results, width='stretch') # Исправлено согласно логам

                # Карта
                if map_points:
                    st.write("### 🗺️ Batch Map View")
                    avg_lat = sum(p['lat'] for p in map_points) / len(map_points)
                    avg_lng = sum(p['lng'] for p in map_points) / len(map_points)
                    
                    st.pydeck_chart(pdk.Deck(
                        map_style="light",
                        initial_view_state=pdk.ViewState(latitude=avg_lat, longitude=avg_lng, zoom=10),
                        layers=[pdk.Layer(
                            "ScatterplotLayer",
                            data=map_points,
                            get_position="[lng, lat]",
                            get_radius=15,
                            get_color="[220, 30, 0, 160]",
                            pickable=True
                        )],
                        tooltip={"html": "{tooltip_text}"}
                    ))

# ==========================================
# SINGLE ANALYSIS
# ==========================================
q_input = st.text_input("Enter Address (e.g. 123 SW 8th St) or Coordinates (e.g. 25.77, -80.19)")

# 1. Инициализируем хранилище данных в сессии
if 'analysis_result' not in st.session_state:
    st.session_state.analysis_result = None

# 2. Фрагмент карты (изолированный поток)
@st.fragment
def map_section(location, match_meta, parcel_info):
    z = parcel_info.get('zoning') if parcel_info else None
    st.write("---")
    with st.container():
        # Показываем статус именно в зоне карты
        # st.info("🛰️ Rendering spatial data...")
        
        clean_addr = match_meta.get('clean_address') or "Unknown Location"
        folio_id = parcel_info.get('id') or "N/A"
        
        # Безопасное извлечение данных зонирования
        z_code = z.get('code') if z else "N/A"
        z_desc = z.get('description') if z else "No data"
        z_juris = z.get('jurisdiction') if z else "N/A"
        
        tooltip_html = f"""
            <div style='font-size: 14px; background-color: #262730; color: white; padding: 10px; border-radius: 5px;'>
                <b style='color:#4dabff; font-size: 16px;'>{clean_addr}</b><br/>
                <hr style='margin: 5px 0; border: 0.2px solid #555;'/>
                <b>Folio:</b> {folio_id}<br/>
                <b>Zoning:</b> {z_code} ({z_desc})<br/>
                <b>Jurisdiction:</b> {z_juris}
            </div>
        """
        
        view = pdk.ViewState(latitude=location['lat'], longitude=location['lng'], zoom=17, pitch=45)
        st.pydeck_chart(pdk.Deck(
            map_style="light",
            initial_view_state=view,
            layers=[pdk.Layer(
                "ScatterplotLayer", 
                data=[location], 
                get_position="[lng, lat]", 
                get_radius=15, 
                get_color="[220, 30, 0]", 
                pickable=True
            )],
            tooltip={"html": tooltip_html}
        ))

# --- ИНТЕРФЕЙС ---
# q_input = st.text_input("Address or Coordinates")

if st.button("Run Analysis", type="primary"):
    if user_api_key and q_input:
        # ШАГ 1: Только получаем данные
        with st.spinner("📡 Fetching API..."):
            raw_res, _ = call_api(user_api_key, q_input)
            # Сохраняем в стейт и ПЕРЕЗАПУСКАЕМ скрипт
            st.session_state.analysis_result = extract_data(raw_res[0] if isinstance(raw_res, list) else raw_res)
            st.rerun() 

# ШАГ 2: Отрисовка (ВНЕ КНОПКИ)
# Этот блок сработает сразу после st.rerun()
if st.session_state.analysis_result:
    data = st.session_state.analysis_result
    
    if data.get('status') == 'success':
        p = data.get('parcel') or {}
        z = p.get('zoning') or {}
        l = data.get('location') or {}
        m = data.get('match_metadata') or {}

        # МГНОВЕННЫЙ ВЫВОД ТЕКСТА
        st.subheader(f"📍 {m.get('clean_address')}")
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Folio ID", p.get('id') or "N/A")
        m2.metric("Zoning Code", z.get('code') or "N/A")
        m3.metric("Anchor ID", (data.get('anchor_id') or "N/A")[:12])

        # 3. TECHNICAL DETAILS
        st.markdown("### Property Details")
        st.markdown(f"""
        <div class="report-text" style="background-color: #f8f9fa; padding: 20px; border-radius: 10px; border-left: 5px solid #1E3A8A;">
            <b>Input Query:</b> {m.get('input_address') or 'N/A'}<br>
            <b>Clean Address:</b> {m.get('clean_address') or 'N/A'}<br>
            <b>Source:</b> {m.get('source') or 'Official data'}<br>
            <hr style="margin: 10px 0; border: 0.1px solid #ddd;">
            <b>Latitude:</b> <code>{l.get('lat') or 'N/A'}</code><br>
            <b>Longitude:</b> <code>{l.get('lng') or 'N/A'}</code><br>
            <b>Jurisdiction:</b> {z.get('jurisdiction') or 'N/A'}<br>
            <hr style="margin: 10px 0; border: 0.1px solid #ddd;">
            <b>Zoning Category:</b> {z.get('category') or 'N/A'}<br>
            <b>Zoning Description:</b> {z.get('description') or 'N/A'}<br>
            <b>Max Height:</b> {z.get('max_height_stories') or 'N/A'} Stories<br>
            <b>Floor Lot Ratio (FLR):</b> {z.get('floor_lot_ratio') or 'N/A'}<br>
            <b>Future Land Use:</b> {p.get('land_use') or 'N/A'}<br>
            <hr style="margin: 10px 0; border: 0.1px solid #ddd;">
            <b>Match Confidence:</b> <span style="color: {'green' if m.get('confidence') == 'HIGH' else '#e67e22'}">{m.get('confidence') or 'UNKNOWN'}</span>
        </div>
        """, unsafe_allow_html=True)

        # 3. EXPORT BUTTON (Excel-friendly CSV)
        # Формируем данные для выгрузки
        # 3. EXPORT TO CSV (Tabular Format)
        # Создаем DataFrame в одну строку — идеально для Excel
        row_data = {
            "folio_id": p.get('id') or "N/A",
            "anchor_id": data.get('anchor_id') or "N/A",
            "zoning_code": z.get('code') or "N/A",
            "zoning_category": z.get('category') or "N/A",
            "zoning_description": z.get('description') or "N/A",
            "future_land_use": p.get('land_use') or "N/A",
            "max_height_stories": z.get('max_height_stories') or "N/A",
            "jurisdiction": z.get('jurisdiction') or "N/A",
            "clean_address": m.get('clean_address') or "N/A",
            "input_address": m.get('input_address') or q_input, # Исправлено val на q_input
            "latitude": l.get('lat'),
            "longitude": l.get('lng'),
            "confidence": m.get('confidence') or "N/A",
            "source": m.get('source') or "N/A"
        }
        
        # Исправленная строка:
        df_export = pd.DataFrame([row_data])
        
        # Создаем буфер в памяти
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_export.to_excel(writer, index=False, sheet_name='Property Analysis')

        st.download_button(
            label="📥 Download Excel Report",
            data=buffer.getvalue(),
            file_name=f"property_{p.get('id')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        # 4. MAP (Placed separately at the bottom for instant text loading)
        map_section(l, m, p)

    elif data.get('status') == 'error':
        # Обработка ошибок типа AMBIGUOUS_ADDRESS
        st.error(f"### ❌ Error: {data.get('error_code')}")
        st.warning(f"**Input:** {data.get('input_address')}")
        st.info(f"**Message:** {data.get('message')}")
