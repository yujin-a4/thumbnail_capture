import streamlit as st
import pandas as pd
import time
import io
import os
import re
import zipfile
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from PIL import Image

# 1. 페이지 설정 및 디자인
st.set_page_config(page_title="YBM AI Lab 썸네일 도구", layout="centered")

st.markdown("""
    <style>
    /* 메인 버튼 스타일 */
    .stButton>button { 
        width: 100%; border-radius: 5px; height: 3em; 
        background-color: #4CAF50; color: white !important; font-weight: bold; 
    }
    /* 리셋 버튼 스타일 */
    .reset-btn>div>button {
        background-color: #f44336 !important; height: 2.5em; margin-bottom: 20px;
    }
    /* URL 입력창 스타일 */
    .stTextArea textarea { 
        font-family: 'Courier New', monospace !important; 
        color: #1E1E1E !important; 
        background-color: #FFFFFF !important; 
    }
    /* 설정 구역 배경색 */
    .settings-box {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 세션 상태 관리 ---
if 'is_running' not in st.session_state:
    st.session_state.is_running = False
if 'processed' not in st.session_state:
    st.session_state.processed = False
if 'zip_data' not in st.session_state:
    st.session_state.zip_data = None
if 'delivery_list' not in st.session_state:
    st.session_state.delivery_list = ""
if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame()

def reset_app():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# --------------------------------

st.title("📸 스마트 섬네일 생성기 v2.4")
st.caption("설정부터 결과까지 한 화면에서 관리하세요.")

# 작업 중 상태 변수
is_active = st.session_state.is_running

# 2. 메인 화면 상단: 전체 초기화 버튼
col_title, col_reset = st.columns([4, 1])
with col_reset:
    st.markdown('<div class="reset-btn">', unsafe_allow_html=True)
    if st.button("🔄 초기화", disabled=is_active):
        reset_app()
    st.markdown('</div>', unsafe_allow_html=True)

# 3. 작업 설정 구역 (기존 사이드바 내용을 메인으로 이동)
st.subheader("⚙️ 1. 작업 설정")
with st.container():
    c1, c2 = st.columns(2)
    with c1:
        wait_time = st.slider("페이지 로딩 대기 시간 (초)", 0, 20, 5, disabled=is_active)
    with c2:
        folder_name = st.text_input("다운로드 폴더명", "thumbnails_result", disabled=is_active)

st.divider()

# 4. 입력 방식 및 데이터 입력
st.subheader("📝 2. 데이터 입력")
input_method = st.radio("입력 방식", ["🔗 URL 텍스트 붙여넣기", "📁 엑셀 파일 업로드"], horizontal=True, disabled=is_active)

df = pd.DataFrame()

if input_method == "📁 엑셀 파일 업로드":
    uploaded_file = st.file_uploader("엑셀 파일 선택", type=["xlsx"], disabled=is_active)
    if uploaded_file:
        df = pd.read_excel(uploaded_file)
else:
    raw_urls = st.text_area("URL 뭉치를 붙여넣으세요", height=150, key="url_input", disabled=is_active)
    example_name = st.text_input("기준 파일명 (예: e_english_k_5_0001)", value="e_english_k_5_0001", disabled=is_active)
    
    if raw_urls and example_name:
        url_list = [u.strip() for u in re.split(r'\s+', raw_urls) if u.strip().startswith('http')]
        match = re.search(r'(.*?)(\d+)$', example_name)
        if match:
            prefix, start_num_str = match.group(1), match.group(2)
            num_len, start_num = len(start_num_str), int(start_num_str)
            names = [f"{prefix}{str(start_num + i).zfill(num_len)}" for i in range(len(url_list))]
            df = pd.DataFrame({"파일명": names, "URL": url_list})
            st.session_state.df = df
        else:
            st.warning("⚠️ 파일명 끝에 숫자가 있어야 합니다.")

# 5. 실행 및 결과 관리
if not df.empty or st.session_state.processed:
    current_df = df if not df.empty else st.session_state.df
    
    with st.expander("📂 작업 대상 리스트 확인"):
        st.dataframe(current_df, use_container_width=True)
    
    def get_driver():
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        if os.name != 'nt': options.binary_location = "/usr/bin/chromium"
        try:
            service = Service(ChromeDriverManager().install())
            return webdriver.Chrome(service=service, options=options)
        except:
            return webdriver.Chrome(options=options)

    if st.button("🚀 캡처 작업 시작", disabled=is_active):
        st.session_state.is_running = True
        st.rerun()

# 실제 프로세스 실행
if st.session_state.is_running and not st.session_state.processed:
    driver = get_driver()
    zip_buffer = io.BytesIO()
    status_text = st.empty()
    progress_bar = st.progress(0)
    
    try:
        with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
            for index, row in st.session_state.df.iterrows():
                file_name, url = str(row.iloc[0]), row.iloc[1]
                status_text.write(f"⏳ **{file_name}** 처리 중... ({index+1}/{len(st.session_state.df)})")
                
                driver.get(url)
                time.sleep(wait_time)
                screenshot = driver.get_screenshot_as_png()
                img = Image.open(io.BytesIO(screenshot)).convert("RGB")
                img = img.resize((416, 234), Image.Resampling.LANCZOS)
                
                img_byte_arr = io.BytesIO()
                img.save(img_byte_arr, format='JPEG')
                zip_file.writestr(f"{file_name}.jpg", img_byte_arr.getvalue())
                progress_bar.progress((index + 1) / len(st.session_state.df))
        
        driver.quit()
        st.session_state.zip_data = zip_buffer.getvalue()
        st.session_state.delivery_list = "\n".join([f"{n}.jpg" for n in st.session_state.df['파일명']])
        st.session_state.processed = True
        st.session_state.is_running = False
        st.rerun()
        
    except Exception as e:
        st.error(f"오류 발생: {e}")
        st.session_state.is_running = False
        if 'driver' in locals(): driver.quit()

# 6. 결과창 (작업 완료 시 노출)
if st.session_state.processed:
    st.divider()
    st.success("✨ 모든 섬네일 생성이 완료되었습니다!")
    st.balloons()
    
    # 결과가 하단에 모여있어 한 눈에 보기 편합니다.
    st.download_button(
        label=f"📂 {folder_name}.zip 다운로드",
        data=st.session_state.zip_data,
        file_name=f"{folder_name}.zip",
        mime="application/zip"
    )
    
    st.subheader("📋 개발사 전달용 목록")
    st.info("아래 코드를 클릭하여 복사하세요.")
    st.code(st.session_state.delivery_list, language="text")