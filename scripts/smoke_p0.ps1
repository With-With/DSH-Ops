# P0 集成冒烟：后端自检 + detect/health API 实测
# 用法: powershell -ExecutionPolicy Bypass -File scripts\smoke_p0.ps1
# 退出码 0 = 全部通过

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
$py = "$root\venv\Scripts\python.exe"
$fail = 0

function Step($name, $block) {
    try { & $block; if ($LASTEXITCODE -ne 0 -and $? -eq $false) { throw "exit $LASTEXITCODE" } }
    catch { Write-Host "  [FAIL] $name : $_" -ForegroundColor Red; $script:fail++; return }
    Write-Host "  [OK] $name" -ForegroundColor Green
}

Write-Host "== 1. manage.py check =="
Push-Location "$root\server"
& $py manage.py check
if ($LASTEXITCODE -ne 0) { Write-Host "[FAIL] check" -ForegroundColor Red; Pop-Location; exit 1 }
Write-Host "  [OK] check" -ForegroundColor Green

Write-Host "== 2. 单元测试 =="
& $py manage.py test apps.runtime_mgr --verbosity 1
if ($LASTEXITCODE -ne 0) { Write-Host "  [FAIL] tests" -ForegroundColor Red; Pop-Location; exit 1 }
Write-Host "  [OK] tests" -ForegroundColor Green

Write-Host "== 3. 启动 dev server =="
$server = Start-Process -FilePath $py -ArgumentList "manage.py","runserver","127.0.0.1:8765","--noreload" -WorkingDirectory "$root\server" -PassThru -WindowStyle Hidden
try {
    Start-Sleep -Seconds 6
    $ready = $false
    foreach ($i in 1..10) {
        try { Invoke-RestMethod "http://127.0.0.1:8765/api/runtimes/" -TimeoutSec 3 | Out-Null; $ready = $true; break } catch { Start-Sleep -Seconds 2 }
    }
    if (-not $ready) { throw "server 未就绪" }

    Write-Host "== 4. detect API（应探测到平台局部运行时 0.1.0-rc.6）=="
    $det = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8765/api/runtimes/detect/" -ContentType "application/json" -Body "{}" -TimeoutSec 60
    $v = $det.detect_result.version; $src = $det.detect_result.detect_source
    Write-Host "  version=$v source=$src status=$($det.instance.status)"
    if ($v -ne "0.1.0-rc.6") { Write-Host "  [WARN] 版本非预期（期望 0.1.0-rc.6）" -ForegroundColor Yellow }
    if ($src -ne "local-runtime") { Write-Host "  [WARN] 来源非 local-runtime（实际 $src），确认 agent/runtime 已安装" -ForegroundColor Yellow }

    Write-Host "== 5. 列表 API =="
    $list = Invoke-RestMethod "http://127.0.0.1:8765/api/runtimes/" -TimeoutSec 10
    $count = if ($list.results) { $list.results.Count } else { $list.Count }
    Write-Host "  runtimes=$count"
    if ($count -lt 1) { throw "列表为空" }

    Write-Host "== 6. 健康检查 API（dsh --dump-default-config）=="
    $rid = if ($list.results) { $list.results[0].id } else { $list[0].id }
    $hc = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8765/api/runtimes/$rid/health_check/" -TimeoutSec 60
    Write-Host "  passed=$($hc.passed) exit=$($hc.exit_code) profile=$($hc.profile_used)"
    if (-not $hc.passed) { Write-Host "  [FAIL] 健康检查未通过: $($hc.stderr)" -ForegroundColor Red; exit 1 }
    Write-Host "  [OK] health check" -ForegroundColor Green
}
finally {
    Write-Host "== 7. 停止 dev server =="
    if (-not $server.HasExited) { Stop-Process -Id $server.Id -Force }
    Pop-Location
}

if ($fail -gt 0) { Write-Host "`n冒烟失败" -ForegroundColor Red; exit 1 }
Write-Host "`nP0 冒烟全部通过" -ForegroundColor Green
