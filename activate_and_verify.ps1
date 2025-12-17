# 가상환경 활성화 및 검증 스크립트
# UTF-8 인코딩 설정
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "`n=== 가상환경 활성화 및 검증 ===" -ForegroundColor Cyan
Write-Host ""

# 현재 스크립트의 디렉토리로 이동
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptPath
Write-Host "작업 디렉토리: $scriptPath" -ForegroundColor Gray
Write-Host ""

# 가상환경 확인
if (Test-Path ".\venv\Scripts\Activate.ps1") {
    Write-Host "✓ 가상환경 발견!" -ForegroundColor Green
    Write-Host ""
    
    # 가상환경 활성화
    Write-Host "가상환경 활성화 중..." -ForegroundColor Yellow
    & ".\venv\Scripts\Activate.ps1"
    
    Write-Host ""
    Write-Host "=== 가상환경 정보 ===" -ForegroundColor Cyan
    Write-Host ""
    
    # Python 버전 확인
    Write-Host "Python 버전:" -ForegroundColor White
    python --version
    Write-Host ""
    
    # pip 버전 확인
    Write-Host "pip 버전:" -ForegroundColor White
    pip --version
    Write-Host ""
    
    # 가상환경 경로 확인
    Write-Host "가상환경 경로:" -ForegroundColor White
    python -c "import sys; print(sys.prefix)"
    Write-Host ""
    
    # 주요 패키지 확인
    Write-Host "=== 설치된 주요 패키지 ===" -ForegroundColor Cyan
    pip list | Select-String -Pattern "streamlit|pandas|numpy|folium|geopandas|shapely"
    Write-Host ""
    
    # requirements.txt와 비교
    if (Test-Path "requirements.txt") {
        Write-Host "=== requirements.txt 확인 ===" -ForegroundColor Cyan
        Get-Content "requirements.txt" | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
        Write-Host ""
    }
    
    Write-Host "✓ 가상환경 활성화 완료!" -ForegroundColor Green
    Write-Host ""
    Write-Host "이제 다음 명령어로 Streamlit을 실행할 수 있습니다:" -ForegroundColor Yellow
    Write-Host "  python -m streamlit run `"251215 ExtractionOfExpertsBehaviorHistroy.py`"" -ForegroundColor White
    Write-Host ""
    
} else {
    Write-Host "✗ 가상환경을 찾을 수 없습니다!" -ForegroundColor Red
    Write-Host ""
    Write-Host "가상환경을 생성하려면 다음 명령어를 실행하세요:" -ForegroundColor Yellow
    Write-Host "  python -m venv venv" -ForegroundColor White
    Write-Host ""
    Write-Host "그 다음 이 스크립트를 다시 실행하세요." -ForegroundColor Yellow
    Write-Host ""
    Read-Host "아무 키나 누르세요..."
}
