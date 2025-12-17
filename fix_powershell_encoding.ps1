# PowerShell 인코딩 문제 해결 스크립트
Write-Host "`n=== PowerShell 한글 경로 문제 해결 ===" -ForegroundColor Cyan
Write-Host ""

# 현재 인코딩 확인
Write-Host "현재 인코딩 설정:" -ForegroundColor Yellow
Write-Host "  Console.OutputEncoding: $([Console]::OutputEncoding.EncodingName)"
Write-Host "  OutputEncoding: $($OutputEncoding.EncodingName)"
Write-Host "  CodePage: $([Console]::OutputEncoding.CodePage)"
Write-Host ""

# UTF-8로 변경
Write-Host "UTF-8로 변경 중..." -ForegroundColor Yellow
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null

Write-Host "변경된 인코딩 설정:" -ForegroundColor Green
Write-Host "  Console.OutputEncoding: $([Console]::OutputEncoding.EncodingName)"
Write-Host "  OutputEncoding: $($OutputEncoding.EncodingName)"
Write-Host "  CodePage: $([Console]::OutputEncoding.CodePage)"
Write-Host ""

# 환경 변수 설정
$env:PYTHONIOENCODING = "utf-8"
$env:STREAMLIT_SERVER_ENCODING = "utf-8"

Write-Host "환경 변수 설정:" -ForegroundColor Green
Write-Host "  PYTHONIOENCODING: $env:PYTHONIOENCODING"
Write-Host "  STREAMLIT_SERVER_ENCODING: $env:STREAMLIT_SERVER_ENCODING"
Write-Host ""

# PowerShell 프로필에 영구적으로 추가할지 물어보기
Write-Host "PowerShell 프로필에 이 설정을 영구적으로 추가하시겠습니까? (Y/N)" -ForegroundColor Yellow
$response = Read-Host

if ($response -eq "Y" -or $response -eq "y") {
    $profilePath = $PROFILE
    
    if (-not (Test-Path $profilePath)) {
        Write-Host "프로필 파일이 없습니다. 생성 중..." -ForegroundColor Yellow
        $profileDir = Split-Path -Parent $profilePath
        if (-not (Test-Path $profileDir)) {
            New-Item -ItemType Directory -Path $profileDir -Force | Out-Null
        }
        New-Item -ItemType File -Path $profilePath -Force | Out-Null
    }
    
    $encodingFix = @"

# 한글 경로 문제 해결 (자동 추가됨)
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
`$OutputEncoding = [System.Text.Encoding]::UTF8
`$env:PYTHONIOENCODING = "utf-8"
`$env:STREAMLIT_SERVER_ENCODING = "utf-8"

"@
    
    $profileContent = Get-Content $profilePath -ErrorAction SilentlyContinue
    if ($profileContent -notmatch "PYTHONIOENCODING") {
        Add-Content -Path $profilePath -Value $encodingFix
        Write-Host "✓ 프로필에 설정이 추가되었습니다!" -ForegroundColor Green
        Write-Host "  다음 PowerShell 세션부터 자동으로 적용됩니다." -ForegroundColor Gray
    } else {
        Write-Host "프로필에 이미 설정이 있습니다." -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "✓ 인코딩 설정 완료!" -ForegroundColor Green
Write-Host "이제 한글 경로가 제대로 작동할 것입니다." -ForegroundColor Cyan
Write-Host ""
