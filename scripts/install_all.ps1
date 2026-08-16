# 一键安装（开发机，Windows PowerShell）
# 用法: powershell -ExecutionPolicy Bypass -File scripts\install_all.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

# 1. Python venv + 后端依赖
if (-not (Test-Path "$root\venv")) {
    python -m venv "$root\venv"
}
& "$root\venv\Scripts\python.exe" -m pip install --upgrade pip -q
& "$root\venv\Scripts\pip.exe" install django">=5.1,<5.3" djangorestframework django-filter django-cors-headers

# 2. 数据库迁移
Push-Location "$root\server"
& "$root\venv\Scripts\python.exe" manage.py migrate
Pop-Location

# 3. 前端依赖
Push-Location "$root\web"
npm install --no-audit --no-fund
Pop-Location

# 4. 平台专用 DSH 运行时（锁版本 0.1.0-rc.6）
Push-Location "$root\agent\runtime"
npm install --no-audit --no-fund
Pop-Location

# 5. 平台 DSH_HOME 目录
New-Item -ItemType Directory -Path "$root\agent\home" -Force | Out-Null

Write-Host "`n安装完成。启动: scripts\start_backend.ps1 + scripts\start_frontend.ps1" -ForegroundColor Green
