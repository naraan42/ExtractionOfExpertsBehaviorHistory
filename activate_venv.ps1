# 가상환경 활성화 스크립트
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptPath

Write-Host "`n=== 가상환경 찾기 및 활성화 ===" -ForegroundColor Cyan
Write-Host ""

# 가능한 가상환경 폴더 이름들 확인
$venvPaths = @("venv", "env", ".venv", "virtualenv")

$found = $false
foreach ($venvPath in $venvPaths) {
    if (Test-Path "$venvPath\Scripts\Activate.ps1") {
        Write-Host "✓ 가상환경 발견: $venvPath" -ForegroundColor Green
        Write-Host "활성화 중..." -ForegroundColor Yellow
        & ".\$venvPath\Scripts\Activate.ps1"
        $found = $true
        break
    }
}

if (-not $found) {
    Write-Host "✗ 가상환경을 찾을 수 없습니다!" -ForegroundColor Red
    Write-Host ""
    Write-Host "다음 폴더들을 확인했습니다:" -ForegroundColor Yellow
    foreach ($venvPath in $venvPaths) {
        Write-Host "  - $venvPath" -ForegroundColor Gray
    }
    Write-Host ""
    Write-Host "가상환경 폴더 이름을 확인하거나, 새로 생성하세요:" -ForegroundColor Yellow
    Write-Host "  python -m venv venv" -ForegroundColor White
    Write-Host ""
    Read-Host "아무 키나 누르세요..."
    exit
}

Write-Host ""
Write-Host "=== 가상환경 정보 ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Python 버전:" -ForegroundColor White
python --version
Write-Host ""
Write-Host "pip 버전:" -ForegroundColor White
pip --version
Write-Host ""
Write-Host "가상환경 경로:" -ForegroundColor White
python -c "import sys; print(sys.prefix)"
Write-Host ""
Write-Host "✓ 가상환경 활성화 완료!" -ForegroundColor Green
Write-Host ""
Write-Host "이제 다음 명령어로 Streamlit을 실행할 수 있습니다:" -ForegroundColor Yellow
Write-Host "  python -m streamlit run `"251215 ExtractionOfExpertsBehaviorHistroy.py`"" -ForegroundColor White
Write-Host ""
