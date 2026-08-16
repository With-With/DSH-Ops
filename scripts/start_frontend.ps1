# 启动前端（Vite dev server :5173，/api 代理到 :8000）
$root = Split-Path -Parent $PSScriptRoot
Push-Location "$root\web"
npm run dev
Pop-Location
