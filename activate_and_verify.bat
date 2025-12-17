@echo off
chcp 65001 >nul
echo.
echo === 가상환경 활성화 및 검증 ===
echo.

cd /d "%~dp0"

if exist "venv\Scripts\activate.bat" (
    echo [가상환경 발견]
    echo.
    echo 가상환경 활성화 중...
    call venv\Scripts\activate.bat
    
    echo.
    echo === 가상환경 정보 ===
    echo.
    echo Python 버전:
    python --version
    echo.
    echo pip 버전:
    pip --version
    echo.
    echo 가상환경 경로:
    python -c "import sys; print(sys.prefix)"
    echo.
    echo === 설치된 주요 패키지 ===
    pip list | findstr /i "streamlit pandas numpy folium geopandas shapely"
    echo.
    
    if exist "requirements.txt" (
        echo === requirements.txt 확인 ===
        type requirements.txt
        echo.
    )
    
    echo [가상환경 활성화 완료]
    echo.
    echo 이제 다음 명령어로 Streamlit을 실행할 수 있습니다:
    echo   python -m streamlit run "251215 ExtractionOfExpertsBehaviorHistroy.py"
    echo.
    
    cmd /k
) else (
    echo [가상환경을 찾을 수 없습니다!]
    echo.
    echo 가상환경을 생성하려면 다음 명령어를 실행하세요:
    echo   python -m venv venv
    echo.
    echo 그 다음 이 스크립트를 다시 실행하세요.
    echo.
    pause
)
