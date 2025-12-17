# Streamlit 앱 실행 스크립트
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptPath

Write-Host "`n=== Streamlit 앱 실행 ===" -ForegroundColor Cyan
Write-Host ""

# 가상환경 활성화 시도
$venvPaths = @("venv", "env", ".venv")
$venvActivated = $false

foreach ($venvPath in $venvPaths) {
    if (Test-Path "$venvPath\Scripts\Activate.ps1") {
        Write-Host "[가상환경 활성화 중: $venvPath]" -ForegroundColor Yellow
        & ".\$venvPath\Scripts\Activate.ps1"
        $venvActivated = $true
        break
    }
}

if (-not $venvActivated) {
    Write-Host "[가상환경을 찾을 수 없습니다. 시스템 Python을 사용합니다.]" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "[Streamlit 앱 실행 중...]" -ForegroundColor Cyan
Write-Host ""

# Streamlit 실행
python -m streamlit run "251215 ExtractionOfExpertsBehaviorHistroy.py"
