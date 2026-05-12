import streamlit as st
import yfinance as yf
import google.generativeai as genai
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import concurrent.futures
import requests
import time

# 1. AI 및 기초 설정
GOOGLE_API_KEY = "AIzaSyDxQnuYzXf31AmJh1uCn_RV9ZP3BKKI8WM"
genai.configure(api_key=GOOGLE_API_KEY)

st.set_page_config(page_title="한투- 꿔니 투자 지휘소", page_icon="🏛️", layout="wide")

# 🎨 [디자인] CSS
st.markdown("""
    <style>
    .sticky-header { position: -webkit-sticky; position: sticky; top: 0; z-index: 1000; background-color: #f1f3f6; padding: 10px 0; border-bottom: 3px solid #d4af37; }
    .header-text { font-size: 1.05rem !important; font-weight: 900 !important; color: #111; text-align: center; }
    .data-cell { display: flex; align-items: center; justify-content: center; height: 100px; font-size: 1.2rem !important; font-weight: 800; text-align: center; margin: 0; }
    .compact-table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 1.1rem; text-align: center; background: white; border-radius: 8px; overflow: hidden; }
    .compact-table th { background-color: #f8f9fa; color: #333; font-weight: 900; padding: 10px; border: 1px solid #eee; }
    .compact-table td { padding: 10px; border: 1px solid #eee; font-weight: bold; }
    hr { margin: 0 !important; border: 0.5px solid #ddd !important; }
    div[data-testid="stHorizontalBlock"]:has(input[type="checkbox"]:checked) { background-color: #E0F7FA !important; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# 🔌 [한투 API] 통신 로직
# ---------------------------------------------------------
def get_kis_token():
    if 'kis_token' in st.session_state: return st.session_state.kis_token
    try:
        url = "https://openapi.koreainvestment.com:9443/oauth2/tokenP"
        body = {"grant_type": "client_credentials", "appkey": st.secrets["kis_api"]["APP_KEY"], "appsecret": st.secrets["kis_api"]["APP_SECRET"]}
        res = requests.post(url, json=body).json()
        if "access_token" in res:
            token = res["access_token"]
            st.session_state.kis_token = token
            return token
        else: return f"토큰발급에러: {res.get('msg1', '이유 모름')}"
    except Exception as e: return "토큰발급에러: 통신 실패"

def get_kis_supply(ticker_6, token):
    if not token: return "<span style='color:#bbb; font-size:0.9rem;'>⚠️ Secrets 필요</span>"
    if "에러:" in token: return f"<span style='color:red; font-size:0.8rem;'>{token}</span>"
    if len(ticker_6) != 6: return "-"
    
    url = "https://openapi.koreainvestment.com:9443/uapi/domestic-stock/v1/quotations/inquire-investor"
    headers = {
        "content-type": "application/json; charset=utf-8", "authorization": f"Bearer {token}",
        "appkey": st.secrets["kis_api"]["APP_KEY"], "appsecret": st.secrets["kis_api"]["APP_SECRET"],
        "tr_id": "FHKST01010900"
    }
    params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": ticker_6}
    
    for attempt in range(3):
        try:
            res = requests.get(url, headers=headers, params=params)
            if res.status_code == 200:
                data = res.json()
                if data.get('rt_cd') == '0':
                    out = data.get('output')
                    if not out: return "<span style='color:#bbb; font-size:0.9rem;'>데이터 없음</span>"
                    if isinstance(out, list): out = out[0] if len(out) > 0 else {}
                    def safe_int(v):
                        try: return int(str(v).replace(',', '').strip()) if v else 0
                        except: return 0
                    prsn, frgn, orgn = safe_int(out.get('prsn_ntby_qty')), safe_int(out.get('frgn_ntby_qty')), safe_int(out.get('orgn_ntby_qty'))
                    def fmt(v):
                        if v > 0: return f"<span style='color:red;'>+{v//1000}k</span>"
                        elif v < 0: return f"<span style='color:blue;'>{v//1000}k</span>"
                        return "-"
                    return f"<div style='font-size:1.1rem; line-height:1.4;'>개: {fmt(prsn)}<br>외: {fmt(frgn)}<br>기: {fmt(orgn)}</div>"
            time.sleep(0.5) 
        except Exception as e: 
            time.sleep(0.5)
    return f"<span style='color:#bbb; font-size:0.9rem;'>수급 미제공</span>"

# ---------------------------------------------------------
# 📊 [데이터 연동] 통합 리스트
# ---------------------------------------------------------
SHEET_STOCKS = {
    "삼성전자": {"ticker": "005930.KS", "sector": "반도체"}, "SK하이닉스": {"ticker": "000660.KS", "sector": "반도체"}, "한미반도체": {"ticker": "042700.KS", "sector": "반도체"}, "SK텔레콤": {"ticker": "017670.KS", "sector": "통신"},
    "효성중공업": {"ticker": "298040.KS", "sector": "전력"}, "HD현대일렉트릭": {"ticker": "267260.KS", "sector": "전력"}, "산일전기": {"ticker": "062040.KS", "sector": "전력"}, "제룡전기": {"ticker": "033100.KQ", "sector": "전력"}, "비츠로셀": {"ticker": "082920.KQ", "sector": "전지"},
    "삼성중공업": {"ticker": "010140.KS", "sector": "조선"}, "HD현대중공업": {"ticker": "329180.KS", "sector": "조선"}, "한화오션": {"ticker": "042660.KS", "sector": "조선"}, "현대로템": {"ticker": "064350.KS", "sector": "방산"}, "한화에어로스페이스": {"ticker": "012450.KS", "sector": "방산"}, "LIG넥스원": {"ticker": "079550.KS", "sector": "방산"}, "두산에너빌리티": {"ticker": "034020.KS", "sector": "원자력"}, "우진": {"ticker": "105840.KS", "sector": "원자력"},
    "레인보우로보틱스": {"ticker": "277810.KQ", "sector": "로봇"}, "로보티즈": {"ticker": "108490.KQ", "sector": "로봇"}, "현대차2우B": {"ticker": "005385.KS", "sector": "자동차"},
    "TIGER 코리아원자력": {"ticker": "461580.KS", "sector": "ETF"}, "SOL AI반도체TOP2플러스": {"ticker": "479630.KS", "sector": "ETF"}, "KODEX AI전력핵심설비": {"ticker": "480310.KS", "sector": "ETF"}
}

if 'manual_stocks' not in st.session_state: st.session_state.manual_stocks = []
if 'compare_set' not in st.session_state: st.session_state.compare_set = set()
if 'menu' not in st.session_state: st.session_state.menu = "💎 관심기업"

@st.cache_data(ttl=60)
def fetch_all_data(tickers):
    results = {}
    token = get_kis_token()
    def get_data(tk):
        try:
            t = yf.Ticker(tk); df = t.history(period="5d", interval="5m")
            if not df.empty: df = df[df.index.date == df.index[-1].date()]
            ticker_6 = tk.split(".")[0]
            time.sleep(0.3) 
            supply_txt = get_kis_supply(ticker_6, token)
            return tk, df, t.info, supply_txt
        except Exception as e: return tk, pd.DataFrame(), {}, f"조회불가"
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(get_data, tk): tk for tk in tickers}
        for future in concurrent.futures.as_completed(futures):
            tk, df, info, sup = future.result()
            results[tk] = {'df': df, 'info': info, 'supply': sup}
    return results

def draw_smart_chart(df, prev):
    if df.empty: return go.Figure()
    df['pct'] = (df['Close'] - prev) / prev * 100
    fig = go.Figure()
    fig.add_shape(type="line", x0=df.index[0], x1=df.index[-1], y0=0, y1=0, line=dict(color="black", width=1.5, dash="dot"))
    for i in range(len(df)-1):
        v = df['pct'].iloc[i]; c = "red" if v > 0.01 else ("blue" if v < -0.01 else "black")
        fig.add_trace(go.Scatter(x=df.index[i:i+2], y=df['pct'].iloc[i:i+2], mode='lines', line=dict(color=c, width=3.5), hoverinfo='none', showlegend=False))
    max_v, min_v = df['pct'].max(), df['pct'].min()
    fig.add_annotation(x=df['pct'].idxmax(), y=max_v, text=f"<b>MAX {max_v:+.1f}%</b>", showarrow=False, font=dict(color="red" if max_v>0 else "blue", size=18), yshift=-12, bgcolor="rgba(255,255,255,0.9)")
    fig.add_annotation(x=df['pct'].idxmin(), y=min_v, text=f"<b>MIN {min_v:+.1f}%</b>", showarrow=False, font=dict(color="red" if min_v>0 else "blue", size=18), yshift=12, bgcolor="rgba(255,255,255,0.9)")
    fig.update_layout(height=120, margin=dict(l=0, r=0, t=0, b=0), xaxis=dict(visible=False), yaxis=dict(visible=False), plot_bgcolor="white")
    return fig

# ---------------------------------------------------------
# ⬅️ 사이드바 & 메뉴
# ---------------------------------------------------------
with st.sidebar:
    st.markdown("<h2 style='color:#d4af37;'>🏛️ 한투- 꿔니 지휘소</h2>", unsafe_allow_html=True)
    st.divider()
    st.session_state.menu = st.radio("메뉴", ["🗺️ 시장 히트맵", "💰 내 자산 확인", "💎 관심기업", "📊 상세 차트 분석"], index=["🗺️ 시장 히트맵", "💰 내 자산 확인", "💎 관심기업", "📊 상세 차트 분석"].index(st.session_state.menu))

# --- [메뉴 1: 관심기업] ---
if st.session_state.menu == "💎 관심기업":
    st.markdown("### ➕ 새로운 종목 뽀개기 (무조건 리스트 1번으로 갑니다)")
    c1, c2, c3, c4 = st.columns([2, 2, 1.5, 1])
    n_n = c1.text_input("종목명 (예: 카카오)")
    n_t = c2.text_input("티커 (예: 035720)")
    n_s = c3.text_input("섹터 (예: IT)")
    if c4.button("추가하기") and n_n and n_t:
        t_full = f"{n_t}.KS" if n_t.isdigit() and len(n_t)==6 else n_t
        st.session_state.manual_stocks.insert(0, {"name": n_n, "ticker": t_full, "sector": n_s if n_s else "수동"})
        st.cache_data.clear(); st.rerun()
    st.divider()

    st.markdown("""<div class="sticky-header"><div style="display: flex; justify-content: space-between; align-items: center; padding: 0 15px;">
        <div style="flex: 1; font-size: 1.6rem; font-weight: 900;">💎 관심종목 뽀개기 리스트</div>
        </div></div>""", unsafe_allow_html=True)
    
    full_list = [{"name": m['name'], "ticker": m['ticker'], "sector": m['sector']} for m in st.session_state.manual_stocks]
    for s_name, s_info in SHEET_STOCKS.items():
        if not any(x['name'] == s_name for x in full_list): full_list.append({"name": s_name, "ticker": s_info['ticker'], "sector": s_info['sector']})

    all_tickers = [item['ticker'] for item in full_list]
    market_data = fetch_all_data(all_tickers)

    btn_c1, btn_c2, btn_c3, btn_c4, btn_c5 = st.columns([1.5, 1, 0.5, 0.5, 0.5])
    with btn_c2:
        sel_sect = st.selectbox("📂 섹터 필터", ["전체"] + sorted(list(set(s['sector'] for s in full_list))), label_visibility="collapsed")
    with btn_c3:
        if st.button("🔄 갱신", use_container_width=True): st.cache_data.clear(); st.rerun()
    with btn_c4:
        if st.button("🗑️ 삭제", use_container_width=True):
            if st.session_state.compare_set:
                st.session_state.manual_stocks = [s for s in st.session_state.manual_stocks if s['name'] not in st.session_state.compare_set]
                st.session_state.compare_set = set(); st.cache_data.clear(); st.rerun()
            else: st.warning("체크 먼저!")
    with btn_c5:
        if st.button("📊 비교", use_container_width=True):
            if st.session_state.compare_set: st.session_state.show_compare = True
            else: st.warning("체크 먼저!")

    if 'show_compare' in st.session_state and st.session_state.show_compare:
        st.subheader(f"🔍 실전 비교 ({', '.join(st.session_state.compare_set)})")
        comp_list = list(st.session_state.compare_set)[:3]
        period_label = st.radio("비교 기간 선택", ["1개월", "3개월", "6개월", "1년"], horizontal=True, index=3)
        period_map = {"1개월": "1mo", "3개월": "3mo", "6개월": "6mo", "1년": "1y"}
        
        comp_tickers = [next((i['ticker'] for i in full_list if i['name']==cn)) for cn in comp_list]
        @st.cache_data(ttl=300)
        def get_comp_data(tickers, period_str):
            res = {}
            for tk in tickers: res[tk] = yf.Ticker(tk).history(period=period_str)
            return res
        
        h_data = get_comp_data(comp_tickers, period_map[period_label])
        fig_comp = go.Figure()
        for cn, tk in zip(comp_list, comp_tickers):
            df_c = h_data[tk]
            if not df_c.empty:
                norm = (df_c['Close'] / df_c['Close'].dropna().iloc[0]) * 100 - 100
                fig_comp.add_trace(go.Scatter(x=norm.index, y=norm, name=cn, line=dict(width=3)))
        st.plotly_chart(fig_comp, use_container_width=True)

        html_table = "<table class='compact-table'><tr><th>비교 항목</th>"
        for cn in comp_list: html_table += f"<th>{cn}</th>"
        html_table += "</tr>"
        
        h_data_1y = get_comp_data(comp_tickers, "1y")
        
        def get_safe_close(df):
            if df.empty: return 0
            valid_closes = df['Close'].dropna()
            return valid_closes.iloc[-1] if not valid_closes.empty else 0

        def row(label, func):
            tr = f"<tr><td>{label}</td>"
            for cn, tk in zip(comp_list, comp_tickers):
                val, is_pct = func(h_data_1y[tk], market_data[tk]['info'])
                if val == "N/A":
                    tr += f"<td>{val}</td>"
                else:
                    c = "red" if is_pct and float(val)>0 else ("blue" if is_pct and float(val)<0 else "black")
                    val_str = f"{float(val):+.1f}%" if is_pct else val
                    tr += f"<td style='color:{c};'>{val_str}</td>"
            return tr + "</tr>"

        html_table += row("현재가", lambda df, inf: (f"{int(get_safe_close(df)):,}원" if get_safe_close(df) > 0 else "N/A", False))
        html_table += row("거래대금", lambda df, inf: (f"{(get_safe_close(df)*inf.get('volume',0))/100000000:,.0f}억" if get_safe_close(df) > 0 else "N/A", False))
        html_table += row("순자산", lambda df, inf: (f"{inf.get('totalAssets',0)/100000000:,.0f}억" if inf.get('totalAssets') else "N/A", False))
        
        def ret(df, days):
            try:
                valid_closes = df['Close'].dropna()
                if len(valid_closes) >= days:
                    return (valid_closes.iloc[-1] - valid_closes.iloc[-days])/valid_closes.iloc[-days]*100
                return 0
            except: return 0

        html_table += row("1개월 수익률", lambda df, inf: (ret(df, 20), True))
        html_table += row("3개월 수익률", lambda df, inf: (ret(df, 60), True))
        html_table += row("6개월 수익률", lambda df, inf: (ret(df, 120), True))
        html_table += row("1년 수익률", lambda df, inf: (ret(df, 240), True))
        
        html_table += "</table>"
        st.markdown(html_table, unsafe_allow_html=True)
        if st.button("닫기"): st.session_state.show_compare = False; st.session_state.compare_set = set(); st.rerun()

    st.markdown("""
        <div class="sticky-header" style="top:0px;">
            <div style="display: flex; width: 100%;">
                <div style="width: 5%;" class="header-text">선택</div>
                <div style="width: 7%;" class="header-text">섹터</div>
                <div style="width: 15%;" class="header-text">종목명</div>
                <div style="width: 12%;" class="header-text">현재가</div>
                <div style="width: 10%;" class="header-text">등락률</div>
                <div style="width: 10%;" class="header-text">거래량</div>
                <div style="width: 10%;" class="header-text">거래대금</div>
                <div style="width: 13%;" class="header-text">수급(k)</div>
                <div style="width: 18%;" class="header-text">실시간 추세</div>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    for item in full_list:
        if sel_sect != "전체" and item['sector'] != sel_sect: continue
        tk = item['ticker']
        if tk not in market_data or market_data[tk]['df'].empty: continue
        
        df, info = market_data[tk]['df'], market_data[tk]['info']
        supply_txt = market_data[tk].get('supply', 'API 에러')
        
        valid_closes = df['Close'].dropna()
        if valid_closes.empty: continue
        now = valid_closes.iloc[-1]
        
        prev = info.get('previousClose', df['Open'].dropna().iloc[0] if not df['Open'].dropna().empty else now)
        pct = (now - prev) / prev * 100 if prev else 0
        
        vol_sum = df['Volume'].sum()
        val_ok = (now * vol_sum) / 100000000 
        color = "red" if pct > 0.01 else ("blue" if pct < -0.01 else "black")

        cols = st.columns([0.5, 0.7, 1.5, 1.2, 1.0, 1.0, 1.0, 1.3, 1.8])
        
        # 💡 [핵심] 체크박스 무한루프 버그 완벽 수정!!
        with cols[0]:
            is_ch = item['name'] in st.session_state.compare_set
            chk = st.checkbox("", key=f"c_{item['name']}", value=is_ch, label_visibility="collapsed")
            
            if chk and not is_ch:
                if len(st.session_state.compare_set) < 3: 
                    st.session_state.compare_set.add(item['name'])
                    st.rerun()
                else: 
                    st.error("3개까지만!")
            elif not chk and is_ch:
                st.session_state.compare_set.remove(item['name'])
                st.rerun()
        
        with cols[1]: st.markdown(f"<div class='data-cell' style='font-size:1.1rem !important; color:gray;'>{item['sector']}</div>", unsafe_allow_html=True)
        with cols[2]: st.markdown(f"<div class='data-cell' style='font-size: 1.3rem !important;'>{item['name']}</div>", unsafe_allow_html=True)
        with cols[3]: st.markdown(f"<div class='data-cell'>{int(now):,}원</div>", unsafe_allow_html=True)
        with cols[4]: st.markdown(f"<div class='data-cell' style='color:{color};'>{'▲' if pct>0 else '▼'}{pct:+.2f}%</div>", unsafe_allow_html=True)
        with cols[5]: st.markdown(f"<div class='data-cell' style='font-size:1.1rem !important;'>{int(vol_sum):,}주</div>", unsafe_allow_html=True)
        with cols[6]: st.markdown(f"<div class='data-cell'>{val_ok:,.0f}억</div>", unsafe_allow_html=True)
        with cols[7]: st.markdown(f"<div class='data-cell'>{supply_txt}</div>", unsafe_allow_html=True)
        with cols[8]: st.plotly_chart(draw_smart_chart(df, prev), use_container_width=True, config={'displayModeBar': False})
        st.markdown("<hr>", unsafe_allow_html=True)

# --- [메뉴 2: 히트맵 / 자산 생략 없이 그대로 둠] ---
elif st.session_state.menu == "🗺️ 시장 히트맵":
    st.markdown("<h1>🗺️ 시장 히트맵</h1>", unsafe_allow_html=True)
    st.write("시장 히트맵 로딩 중...") 
    hm_data = []
    for s_name, s_info in SHEET_STOCKS.items():
        try:
            t = yf.Ticker(s_info['ticker']); h = t.history(period="2d")
            c = ((h['Close'].iloc[-1]-h['Close'].iloc[-2])/h['Close'].iloc[-2])*100
            hm_data.append({"종목": s_name, "섹터": s_info['sector'], "변동률": c, "시총": t.info.get('marketCap', 1)})
        except: continue
    if hm_data:
        st.plotly_chart(px.treemap(pd.DataFrame(hm_data), path=[px.Constant("Market"), '섹터', '종목'], values='시총', color='변동률', color_continuous_scale=['blue', '#EEEEEE', 'red'], color_continuous_midpoint=0), use_container_width=True)

elif st.session_state.menu == "💰 내 자산 확인":
    st.markdown("<h1>💰 내 자산 확인</h1>", unsafe_allow_html=True)
    asset_data = [{"섹터": "반도체", "금액": 158168785}, {"섹터": "조선", "금액": 139882350}, {"섹터": "전력", "금액": 69658560}]
    st.metric("총 자산", "약 5.25억 원", "+15.4%")
    st.plotly_chart(px.pie(pd.DataFrame(asset_data), values='금액', names='섹터', hole=0.4), use_container_width=True)

# ---------------------------------------------------------
# 💡 트레이딩뷰 파인스크립트(DC SYS A+) 파이썬 변환 이식
# ---------------------------------------------------------
elif st.session_state.menu == "📊 상세 차트 분석":
    st.markdown("<h1 style='color:#2962FF;'>📊 시스템 트레이딩 (DC SYS A+ STOP)</h1>", unsafe_allow_html=True)
    
    full_list = st.session_state.manual_stocks + [{"name": k, "ticker": v["ticker"]} for k, v in SHEET_STOCKS.items()]
    sel_name = st.selectbox("분석 종목 선택", [s['name'] for s in full_list])
    
    if sel_name:
        tk_str = next((item['ticker'] for item in full_list if item['name'] == sel_name), None)
        
        with st.spinner("트레이딩뷰 데이터를 파이썬으로 계산 중입니다..."):
            hist = yf.Ticker(tk_str).history(period="1y")
            
            if not hist.empty:
                length = 20
                atrLen = 14
                atrMult = 1.5
                
                hist['Upper'] = hist['High'].rolling(length).max()
                hist['Lower'] = hist['Low'].rolling(length).min()
                hist['Basis'] = (hist['Upper'] + hist['Lower']) / 2
                
                hist['refUpper'] = hist['Upper'].shift(1)
                hist['refLower'] = hist['Lower'].shift(1)
                hist['refUpper_prev'] = hist['Upper'].shift(2)
                hist['refLower_prev'] = hist['Lower'].shift(2)
                
                hist['H-L'] = hist['High'] - hist['Low']
                hist['H-C'] = abs(hist['High'] - hist['Close'].shift(1))
                hist['L-C'] = abs(hist['Low'] - hist['Close'].shift(1))
                hist['TR'] = hist[['H-L', 'H-C', 'L-C']].max(axis=1)
                hist['ATR'] = hist['TR'].rolling(atrLen).mean()
                
                buy_x, buy_y = [], []
                sell_x, sell_y = [], []
                stop_x, stop_y = [], []
                
                pos = 0 
                entry_price = np.nan
                
                for i in range(20, len(hist)):
                    c = hist['Close'].iloc[i]
                    c_prev = hist['Close'].iloc[i-1]
                    
                    rUp = hist['refUpper'].iloc[i]
                    rDn = hist['refLower'].iloc[i]
                    rUp_prev = hist['refUpper_prev'].iloc[i]
                    rDn_prev = hist['refLower_prev'].iloc[i]
                    
                    basis = hist['Basis'].iloc[i]
                    atr = hist['ATR'].iloc[i]
                    
                    longEntryRaw = (c > rUp) and (c_prev <= rUp_prev)
                    shortEntryRaw = (c < rDn) and (c_prev >= rDn_prev)
                    
                    longStop, shortStop = False, False
                    if pos == 1:
                        longAtrStop = entry_price - (atr * atrMult)
                        if (c < basis) or (c <= longAtrStop) or (c < rDn):
                            longStop = True
                            pos = 0; entry_price = np.nan
                            stop_x.append(hist.index[i])
                            stop_y.append(hist['High'].iloc[i] + (hist['High'].iloc[i] * 0.02))
                    
                    elif pos == -1:
                        shortAtrStop = entry_price + (atr * atrMult)
                        if (c > basis) or (c >= shortAtrStop) or (c > rUp):
                            shortStop = True
                            pos = 0; entry_price = np.nan
                            stop_x.append(hist.index[i])
                            stop_y.append(hist['Low'].iloc[i] - (hist['Low'].iloc[i] * 0.02))
                    
                    if pos == 0:
                        if longEntryRaw:
                            pos = 1; entry_price = c
                            buy_x.append(hist.index[i])
                            buy_y.append(hist['Low'].iloc[i] - (hist['Low'].iloc[i] * 0.03))
                        elif shortEntryRaw:
                            pos = -1; entry_price = c
                            sell_x.append(hist.index[i])
                            sell_y.append(hist['High'].iloc[i] + (hist['High'].iloc[i] * 0.03))
                
                fig = go.Figure()
                fig.add_trace(go.Candlestick(x=hist.index, open=hist['Open'], high=hist['High'], low=hist['Low'], close=hist['Close'], name="캔들"))
                fig.add_trace(go.Scatter(x=hist.index, y=hist['Upper'], line=dict(color='rgba(41, 98, 255, 0.5)', width=1), name="Upper", showlegend=False))
                fig.add_trace(go.Scatter(x=hist.index, y=hist['Lower'], line=dict(color='rgba(41, 98, 255, 0.5)', width=1), fill='tonexty', fillcolor='rgba(33, 150, 243, 0.1)', name="Lower", showlegend=False))
                fig.add_trace(go.Scatter(x=hist.index, y=hist['Basis'], line=dict(color='rgba(255, 109, 0, 0.8)', width=1.5, dash='dot'), name="Basis", showlegend=False))
                
                if buy_x:
                    fig.add_trace(go.Scatter(x=buy_x, y=buy_y, mode='markers+text', marker=dict(symbol='triangle-up', size=12, color='green'), text=["BUY"]*len(buy_x), textposition="bottom center", textfont=dict(color='green', size=11, weight='bold'), name="BUY"))
                if sell_x:
                    fig.add_trace(go.Scatter(x=sell_x, y=sell_y, mode='markers+text', marker=dict(symbol='triangle-down', size=12, color='red'), text=["SELL"]*len(sell_x), textposition="top center", textfont=dict(color='red', size=11, weight='bold'), name="SELL"))
                if stop_x:
                    fig.add_trace(go.Scatter(x=stop_x, y=stop_y, mode='markers+text', marker=dict(symbol='x', size=10, color='black'), text=["STOP"]*len(stop_x), textposition="middle right", textfont=dict(color='black', size=10), name="STOP"))
                
                fig.update_layout(height=650, title=f"[{sel_name}] Donchian System A+ (1년 시뮬레이션)", xaxis_rangeslider_visible=False, template="plotly_white", margin=dict(l=20, r=20, t=50, b=20))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.error("데이터를 불러오지 못했습니다.")
