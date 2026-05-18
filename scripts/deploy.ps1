# deploy.ps1
# knowledge-hub を GitHub Pages へコミット＆プッシュするヘルパースクリプト
# 使い方: .\scripts\deploy.ps1 [-Message "任意のコミットメッセージ"]

param(
    [string]$Message = ""
)

Set-Location (Split-Path $PSScriptRoot -Parent)

$date = Get-Date -Format "yyyy-MM-dd HH:mm"
if (-not $Message) {
    $Message = "docs: update $date"
}

Write-Host "=== knowledge-hub deploy ===" -ForegroundColor Cyan
Write-Host "Message: $Message"

# 変更確認
$status = git status --short
if (-not $status) {
    Write-Host "変更なし。デプロイをスキップします。" -ForegroundColor Yellow
    exit 0
}

Write-Host "`n変更ファイル:"
git status --short

# ステージング（inbox以外）
git add index.html assets/ scripts/ CHANGELOG.html Personal_Dashboard.html search.html
git add *.html

# コミット
git commit -m $Message
if ($LASTEXITCODE -ne 0) {
    Write-Host "コミット失敗" -ForegroundColor Red
    exit 1
}

# プッシュ
git push origin main
if ($LASTEXITCODE -ne 0) {
    Write-Host "プッシュ失敗" -ForegroundColor Red
    exit 1
}

Write-Host "`nデプロイ完了！" -ForegroundColor Green
Write-Host "公開URL: https://dx-nexus.github.io/knowledge-hub/"
