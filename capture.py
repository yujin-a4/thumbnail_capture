import streamlit as st
import pandas as pd
import time
import io
import os
import zipfile
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from PIL import Image

# 1. 페이지 레이아웃 및 디자인 설정
st.set_page_config(page_title="YBM AI Lab 썸네일 도구", layout="centered")

# CSS를 이용해 UI 디자인 개선
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #4CAF50; color: white; font-weight: bold; }
    .stProgress .st-bo { background-color: #4CAF50; }
    </style>
    """, unsafe_allow_html=True)

st.title("📸 섬네일 자동 생성기")
st.caption("엑셀 파일을 업로드하여 전자저작물 섬네일을 한 번에 생성하세요.")

# 2. 사이드바: 설정 영역
st.sidebar.header("⚙️ 작업 설정")

# 페이지 로딩 대기 시간: 0~20초, 기본값 5초 (요청 반영)
wait_time = st.sidebar.slider("링크별 페이지 로딩 대기 시간 (초)", 0, 20, 5)

# 저장될 폴더(ZIP 파일) 이름 설정 (요청 반영)
folder_name = st.sidebar.text_input("결과물 폴더명 설정", "thumbnails_result")

st.sidebar.divider()
st.sidebar.info(f"설정된 대기 시간: {wait_time}초\n\n결과 파일: {folder_name}.zip")

# 3. 셀레니움 드라이버 설정 (서버 환경 대응)
def get_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    
    # 배포 서버(리눅스) 환경일 경우 크롬 경로 명시
    if os.name != 'nt': 
        options.binary_location = "/usr/bin/chromium"

    try:
        # 로컬 환경에서 드라이버 자동 설치 시도
        service = Service(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=options)
    except Exception:
        # 서버 환경에서는 설치된 기본 드라이버 사용
        return webdriver.Chrome(options=options)

# 4. 메인 화면: 파일 업로드 영역
uploaded_file = st.file_uploader("엑셀 파일을 업로드하세요 (파일명, URL 순서)", type=["xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    
    with st.expander("📂 업로드된 데이터 확인하기"):
        st.dataframe(df, use_container_width=True)
    
    # 실행 버튼
    if st.button("🚀 캡처 작업 시작"):
        driver = get_driver()
        zip_buffer = io.BytesIO()
        
        # 상태 표시용 컨테이너
        status_text = st.empty()
        progress_bar = st.progress(0)
        
        try:
            with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                for index, row in df.iterrows():
                    file_name = str(row[0])
                    url = row[1]
                    
                    status_text.write(f"⏳ **{file_name}** 처리 중... ({index+1}/{len(df)})")
                    
                    try:
                        driver.get(url)
                        time.sleep(wait_time) # 설정된 대기 시간만큼 대기
                        
                        # 스크린샷 캡처
                        screenshot = driver.get_screenshot_as_png()
                        img = Image.open(io.BytesIO(screenshot)).convert("RGB")
                        
                        # 416x234 크기로 리사이징 (기존 로직 유지)
                        img = img.resize((416, 234), Image.Resampling.LANCZOS)
                        
                        # 메모리 내에서 이미지 데이터 생성
                        img_byte_arr = io.BytesIO()
                        img.save(img_byte_arr, format='JPEG')
                        
                        # 설정한 파일명으로 ZIP에 추가
                        zip_file.writestr(f"{file_name}.jpg", img_byte_arr.getvalue())
                        
                    except Exception as e:
                        st.error(f"❌ {file_name} 처리 중 오류 발생: {e}")
                    
                    progress_bar.progress((index + 1) / len(df))
            
            driver.quit()
            
            st.success("✨ 모든 작업이 완료되었습니다!")
            st.balloons()
            
            # 다운로드 버튼
            st.download_button(
                label=f"📂 {folder_name}.zip 다운로드",
                data=zip_buffer.getvalue(),
                file_name=f"{folder_name}.zip",
                mime="application/zip"
            )
            
        except Exception as global_e:
            st.error(f"시스템 오류: {global_e}")
            if 'driver' in locals():
                driver.quit()