# 本机打包 kiro-zh.exe
# 用法：在仓库根目录执行  pwsh -File packaging/build.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Push-Location $root
try {
    if (-not (Test-Path ".venv-build")) {
        uv venv .venv-build --python 3.12
    }
    uv pip install --python .venv-build/Scripts/python.exe pyinstaller | Out-Null

    .venv-build/Scripts/python.exe -m PyInstaller `
        --onefile --noconfirm --clean `
        --name kiro-zh `
        --paths scripts `
        --add-data "assets;assets" `
        --distpath dist --workpath build `
        packaging/kiro_zh.py

    Write-Host "`n产物：$root\dist\kiro-zh.exe"
} finally {
    Pop-Location
}
