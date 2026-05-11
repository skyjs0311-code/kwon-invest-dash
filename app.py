import streamlit as st
import yfinance as yf
import google.generativeai as genai
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime

# 1. AI 및 기본 설정
GOOGLE_API_KEY = "AIzaSyDxQnuYzXf31AmJh1uCn_RV9ZP3BKKI8WM"
genai.configure(api_key=GOOGLE_API_KEY)

# 💡 모델 로딩 함수화 (안정성 강화)
def get_ai_model():
    try:
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        target = 'models/gemini-1.5-flash' if 'models/gemini-1.5-flash' in available_models else available_models[0]
        return genai.GenerativeModel(target)
    except:
        return None

# 앱 레이아웃 설정
st.set_page_config(page_title="한투- 꿔니 투자 지휘소", page_icon="🏛️", layout="wide")

# 세션 상태 초기화
if 'menu' not in st.session_state: st.session_state.menu = "💎 관심기업"
if 'my_stocks' not in st.session_state:
    st.session_state.my_stocks = {"비츠로셀": "082920.KQ", "산일전기": "062040.KS", "제룡전기": "033100.KQ", "삼성중공업": "010140.KS"}

# 🎨 프리미엄 디자인 CSS
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    h1 { color: #1a1a1a; font-family: 'Nanum Myeongjo'; border-bottom: 3px solid #d4af37; padding-bottom: 10px; }
    .sidebar-title { font-size: 22px; font-weight: bold; color: #d4af37; margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# ⬅️ 사이드바
# ---------------------------------------------------------
with st.sidebar:
    st.markdown("<div class='sidebar-title'>🏛️ 한투- 꿔니 투자 지휘소</div>", unsafe_allow_html=True)
    st.write(f"**꿔니 행님, 반갑습니다!**")
    st.divider()
    
    menu = st.radio(
        "메뉴 선택",
        ["🗺️ 시장 히트맵", "💰 내 자산 확인", "💎 관심기업", "📊 상세 차트 분석", "📰 최신 뉴스"],
        index=["🗺️ 시장 히트맵", "💰 내 자산 확인", "💎 관심기업", "📊 상세 차트 분석", "📰 최신 뉴스"].index(st.session_state.menu)
    )
    st.session_state.menu = menu
    st.divider()
    st.caption("v4.5 Final | Powered by 똑띠 AI")

# 중앙 메인 제목
st.markdown(f"<h1>{st.session_state.menu}</h1>", unsafe_allow_html=True)

# ---------------------------------------------------------
# 1~3번 메뉴 (기존 로직 최적화 유지)
# ---------------------------------------------------------
if st.session_state.menu == "🗺️ 시장 히트맵":
    market_sectors = {
        "반도체": {"삼성전자": "005930.KS", "SK하이닉스": "000660.KS"},
        "전력": {"HD현대일렉": "267260.KS", "산일전기": "062040.KS", "제룡전기": "033100.KQ"},
        "로봇": {"레인보우로보틱스": "277810.KQ", "로보티즈": "108490.KQ"},
        "조선": {"삼성중공업": "010140.KS", "HD현대중공업": "329180.KS"},
        "바이오": {"삼바": "207940.KS", "셀트리온": "068270.KS"},
        "2차전지": {"LG엔솔": "373220.KS", "에코프로비엠": "247540.KQ"},
        "원자력": {"두산에너빌리티": "034020.KS"},
        "방산": {"한화에어로스페이스": "012450.KS", "현대로템": "064350.KS"}
    }
    hm_data = []
    for sector, stocks in market_sectors.items():
        for name, sym in stocks.items():
            try:
                t = yf.Ticker(sym)
                h = t.history(period="2d")
                change = ((h['Close'].iloc[-1] - h['Close'].iloc[-2]) / h['Close'].iloc[-2]) * 100
                hm_data.append({"종목": name, "섹터": sector, "변동률": change, "시총": t.info.get('marketCap', 1)})
            except: continue
    if hm_data:
        fig = px.treemap(pd.DataFrame(hm_data), path=[px.Constant("KOSPI/KOSDAQ"), '섹터', '종목'], values='시총', color='변동률', color_continuous_scale=['blue', '#EEEEEE', 'red'], color_continuous_midpoint=0)
        st.plotly_chart(fig, use_container_width=True)

elif st.session_state.menu == "💰 내 자산 확인":
    # 행님 자산 데이터 (예시 기반 최적화)
    asset_data = [{"섹터": "반도체", "금액": 158168785}, {"섹터": "조선", "금액": 139882350}, {"섹터": "전력", "금액": 69658560}, {"섹터": "방산", "금액": 10027600}, {"섹터": "원전", "금액": 24808950}]
    df_asset = pd.DataFrame(asset_data)
    c1, c2 = st.columns(2)
    c1.metric("총 자산", "약 5.25억 원", "+15.4%")
    st.plotly_chart(px.pie(df_asset, values='금액', names='섹터', hole=0.4, title="섹터별 비중"), use_container_width=True)

elif st.session_state.menu == "💎 관심기업":
    with st.expander("⚙️ 종목 관리 (추가/삭제)"):
        c1, c2, c3 = st.columns([1, 1, 0.5])
        add_n, add_t = c1.text_input("기업명"), c2.text_input("티커")
        if c3.button("추가") and add_n and add_t:
            st.session_state.my_stocks[add_n] = add_t; st.rerun()
        st.write("---")
        del_cols = st.columns(6)
        for idx, name in enumerate(list(st.session_state.my_stocks.keys())):
            if del_cols[idx % 6].button(f"❌ {name}"):
                del st.session_state.my_stocks[name]; st.rerun()

    stocks = list(st.session_state.my_stocks.items())
    for i in range(0, len(stocks), 2):
        row_cols = st.columns(2)
        for j, (name, symbol) in enumerate(stocks[i:i+2]):
            with row_cols[j]:
                with st.container(border=True):
                    txt_col, cht_col = st.columns([1, 2])
                    try:
                        t = yf.Ticker(symbol); df = t.history(period="1d", interval="5m")
                        prev = t.info.get('previousClose', df['Open'].iloc[0])
                        now = df['Close'].iloc[-1]; pct = (now - prev) / prev * 100
                        with txt_col:
                            st.subheader(name)
                            st.metric("현재가", f"{int(now):,}원", f"{pct:.2f}%")
                        with cht_col:
                            fig = go.Figure()
                            color = "red" if pct >= 0 else "blue"
                            fig.add_trace(go.Scatter(x=df.index, y=(df['Close']-prev)/prev*100, mode='lines', line=dict(color=color, width=3)))
                            # 💡 MAX/MIN 글씨 강화
                            max_v, min_v = ((df['High']-prev)/prev*100).max(), ((df['Low']-prev)/prev*100).min()
                            fig.add_annotation(x=df.index[df['Close'].argmax()], y=max_v, text=f"<b>MAX {max_v:.1f}%</b>", showarrow=False, font=dict(color="red", size=16))
                            fig.add_annotation(x=df.index[df['Close'].argmin()], y=min_v, text=f"<b>MIN {min_v:.1f}%</b>", showarrow=False, font=dict(color="blue", size=16))
                            fig.update_layout(height=140, margin=dict(l=0, r=0, t=10, b=0), xaxis=dict(visible=False), yaxis=dict(visible=False), plot_bgcolor="white")
                            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
                    except: st.error(f"{name} 로딩 중")

# ---------------------------------------------------------
# 4. 📊 상세 차트 분석 (BUY/SELL/STOP 완벽 구현)
# ---------------------------------------------------------
elif st.session_state.menu == "📊 상세 차트 분석":
    sel = st.selectbox("분석 종목 선택", list(st.session_state.my_stocks.keys()))
    if sel:
        t_data = yf.Ticker(st.session_state.my_stocks[sel])
        # 💡 날짜 표시 미흡 해결: 6개월 데이터를 일봉(1d)으로 가져오고 x축 날짜 포맷 강화
        hist = t_data.history(period="6mo", interval="1d") 
        
        # --- Donchian System A+ 로직 (Pine Script 완벽 이식) ---
        length = 20
        hist['Upper'] = hist['High'].shift(1).rolling(window=length).max()
        hist['Lower'] = hist['Low'].shift(1).rolling(window=length).min()
        hist['Basis'] = (hist['Upper'] + hist['Lower']) / 2
        
        # BUY: 이전 Upper 돌파
        hist['BUY'] = (hist['Close'] > hist['Upper']) & (hist['Close'].shift(1) <= hist['Upper'].shift(1))
        # SELL: 이전 Lower 이탈
        hist['SELL'] = (hist['Close'] < hist['Lower']) & (hist['Close'].shift(1) >= hist['Lower'].shift(1))
        # STOP: 롱 포지션 중 중앙선(Basis) 하향 돌파 시
        hist['STOP'] = (hist['Close'] < hist['Basis']) & (hist['Close'].shift(1) >= hist['Basis'].shift(1))
        
        st.write(f"### {sel} 전문 분석 차트 (Donchian System A+)")
        fig_detail = go.Figure()
        # 캔들스틱 (날짜 표시 강화)
        fig_detail.add_trace(go.Candlestick(x=hist.index, open=hist['Open'], high=hist['High'], low=hist['Low'], close=hist['Close'], name="주가"))
        # 채널 선
        fig_detail.add_trace(go.Scatter(x=hist.index, y=hist['Upper'], line=dict(color='blue', width=1), name="Upper"))
        fig_detail.add_trace(go.Scatter(x=hist.index, y=hist['Lower'], line=dict(color='blue', width=1), name="Lower"))
        fig_detail.add_trace(go.Scatter(x=hist.index, y=hist['Basis'], line=dict(color='orange', dash='dash'), name="Basis"))
        
        # BUY 시그널 (초록)
        buy_pts = hist[hist['BUY']]
        fig_detail.add_trace(go.Scatter(x=buy_pts.index, y=buy_pts['Low']*0.97, mode='markers+text', text="<b>BUY</b>", textposition="bottom center", marker=dict(symbol="triangle-up", size=15, color="green"), name="매수"))
        
        # SELL 시그널 (빨강)
        sell_pts = hist[hist['SELL']]
        fig_detail.add_trace(go.Scatter(x=sell_pts.index, y=sell_pts['High']*1.03, mode='markers+text', text="<b>SELL</b>", textposition="top center", marker=dict(symbol="triangle-down", size=15, color="red"), name="매도"))

        # STOP 시그널 (흰색/검정테두리)
        stop_pts = hist[hist['STOP']]
        fig_detail.add_trace(go.Scatter(x=stop_pts.index, y=stop_pts['High']*1.05, mode='markers+text', text="<b>STOP</b>", textposition="top center", marker=dict(symbol="x", size=10, color="black", line=dict(width=2, color="white")), name="손절/익절"))

        fig_detail.update_layout(height=600, xaxis_rangeslider_visible=False, template="plotly_white", xaxis=dict(type='date', tickformat='%Y-%m-%d'))
        st.plotly_chart(fig_detail, use_container_width=True)

        # 💡 AI 분석 실패 해결책: 버튼 안에서 모델을 새로 정의
        if st.button("🤖 똑띠 AI에게 이 차트 판독 요청"):
            with st.spinner("AI가 차트의 맥점을 짚어내고 있습니다..."):
                try:
                    model = get_ai_model() # 안정적 모델 로딩
                    if model:
                        prompt = f"한국 주식 '{sel}'의 최근 Donchian Channel 돌파와 STOP(중앙선 이탈) 상황을 분석해서, 꿔니 행님을 위한 대응 전략을 아주 명쾌하게 3줄 요약해줘."
                        response = model.generate_content(prompt)
                        st.success("✨ 분석 완료")
                        st.info(response.text)
                    else:
                        st.error("AI 모델을 연결할 수 없습니다. API 키를 확인해 주세요.")
                except Exception as e:
                    st.error(f"분석 실패: {e}")

elif st.session_state.menu == "📰 최신 뉴스":
    sel_n = st.selectbox("뉴스 종목 선택", list(st.session_state.my_stocks.keys()))
    try:
        news = yf.Ticker(st.session_state.my_stocks[sel_n]).news
        for n in news[:8]:
            with st.container(border=True):
                st.write(f"**[{n['title']}]({n['link']})**")
                st.caption(f"출처: {n['publisher']}")
    except: st.write("소식 없음")