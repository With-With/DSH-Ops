# 启动后端（Django dev server :8000）
$root = Split-Path -Parent $PSScriptRoot
Push-Location "$root\server"
& "$root\venv\Scripts\python.exe" manage.py runserver 0.0.0.0:8001
Pop-Location
