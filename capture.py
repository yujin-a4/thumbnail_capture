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

# 1. 페이지 레이아웃 및 디자인
st.set_page_config(page_title="YBM AI Lab 썸네일 도구", layout="centered")

st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #4CAF50; color: white; font-weight: bold; }
    .stTextArea>div>div>textarea { background-color: #f0f2f6; font-family: monospace; }
    .result-box { background-color: #e8f5e9; padding: 15px; border-radius: 10px; border: 1px solid #4CAF50; }
    </style>
    """, unsafe_allow_html=True)

st.title("📸 스마트 섬네일 생성기 v2")
st.caption("예시 파일명 하나만 입력하면 번호를 자동으로 매겨드립니다.")

# 2. 사이드바 설정
st.sidebar.header("⚙️ 작업 설정")
wait_time = st.sidebar.slider("링크별 페이지 로딩 대기 시간 (초)", 0, 20, 5)
folder_name = st.sidebar.text_input("결과물 폴더명 설정", "thumbnails_result")

# 3. 입력 방식 선택
input_method = st.radio("입력 방식 선택", ["🔗 URL 텍스트 붙여넣기", "📁 엑셀 파일 업로드"])

df = pd.DataFrame()

if input_method == "📁 엑셀 파일 업로드":
    uploaded_file = st.file_uploader("엑셀 파일을 업로드하세요", type=["xlsx"])
    if uploaded_file:
        df = pd.read_excel(uploaded_file)
else:
    raw_urls = st.text_area("개발사에서 받은 URL 뭉치를 붙여넣으세요", height=150, placeholder="https://...\nhttps://...")
    example_name = st.text_input("예시 파일명을 입력하세요", value="e_english_k_5_0001", help="번호가 포함된 첫 번째 파일명을 입력하세요.")
    
    if raw_urls and example_name:
        # URL 추출
        url_list = [u.strip() for u in re.split(r'\s+', raw_urls) if u.strip().startswith('http')]
        
        # 파일명 자동 생성 로직 (정규표현식으로 숫자 부분 분리)
        match = re.search(r'(.*?)(\d+)$', example_name)
        if match:
            prefix = match.group(1) # e_english_k_5_
            start_num_str = match.group(2) # 0001
            num_len = len(start_num_str) # 4자릿수 보존
            start_num = int(start_num_str)
            
            names = [f"{prefix}{str(start_num + i).zfill(num_len)}" for i in range(len(url_list))]
            df = pd.DataFrame({"파일명": names, "URL": url_list})
            st.success(f"총 {len(df)}개의 URL과 파일명이 준비되었습니다.")
        else:
            st.error("파일명 끝에 숫자가 포함되어야 자동으로 번호를 매길 수 있습니다.")

# 4. 캡처 로직
if not df.empty:
    with st.expander("📂 생성될 파일 목록 미리보기"):
        st.dataframe(df, use_container_width=True)
    
    def get_driver():
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        if os.name != 'nt': options.binary_location = "/usr/bin/chromium"
        try:
            service = Service(ChromeDriverManager().install())
            return webdriver.Chrome(service=service, options=options)
        except:
            return webdriver.Chrome(options=options)

    if st.button("🚀 캡처 작업 시작"):
        driver = get_driver()
        zip_buffer = io.BytesIO()
        status_text = st.empty()
        progress_bar = st.progress(0)
        
        try:
            with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                for index, row in df.iterrows():
                    file_name = str(row.iloc[0])
                    url = row.iloc[1]
                    status_text.write(f"⏳ **{file_name}** 처리 중... ({index+1}/{len(df)})")
                    
                    try:
                        driver.get(url)
                        time.sleep(wait_time)
                        screenshot = driver.get_screenshot_as_png()
                        img = Image.open(io.BytesIO(screenshot)).convert("RGB")
                        img = img.resize((416, 234), Image.Resampling.LANCZOS)
                        
                        img_byte_arr = io.BytesIO()
                        img.save(img_byte_arr, format='JPEG')
                        zip_file.writestr(f"{file_name}.jpg", img_byte_arr.getvalue())
                    except Exception as e:
                        st.error(f"❌ {file_name} 실패: {e}")
                    progress_bar.progress((index + 1) / len(df))
            
            driver.quit()
            st.success("✨ 모든 작업이 완료되었습니다!")
            st.balloons()
            
            # 다운로드 버튼
            st.download_button(label=f"📂 {folder_name}.zip 다운로드", data=zip_buffer.getvalue(), file_name=f"{folder_name}.zip", mime="application/zip")
            
            # 5. 개발사 전달용 목록 생성 (파일명.jpg)
            st.divider()
            st.subheader("📋 개발사 전달용 파일명 목록")
            st.info("아래 목록을 복사해서 그대로 전달하세요.")
            # .jpg를 붙인 목록 생성
            jpg_names = "\n".join([f"{name}.jpg" for name in df['파일명']])
            st.text_area("파일명 목록 (복사 가능)", value=jpg_names, height=200)

        except Exception as global_e:
            st.error(f"오류 발생: {global_e}")
            if 'driver' in locals(): driver.quit()