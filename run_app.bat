@echo off
chcp 65001 >nul
echo.
echo === Streamlit 앱 실행 ===
echo.

cd /d "%~dp0"

REM 가상환경 활성화 시도
if exist "venv\Scripts\activate.bat" (
    echo [가상환경 활성화 중...]
    call venv\Scripts\activate.bat
) else if exist "env\Scripts\activate.bat" (
    echo [가상환경 활성화 중...]
    call env\Scripts\activate.bat
) else (
    echo [가상환경을 찾을 수 없습니다. 시스템 Python을 사용합니다.]
)

echo.
echo [Streamlit 앱 실행 중...]
echo.

REM Streamlit 실행
python -m streamlit run "251215 ExtractionOfExpertsBehaviorHistroy.py"

pause
