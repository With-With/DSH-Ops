# P1 集成冒烟：录制->解析->trace回放->元素先搜后建->任务集状态机 全链
# 用法: powershell -ExecutionPolicy Bypass -File scripts\smoke_p1.ps1
# 注意：演示录制脚本 goto 指向 127.0.0.1:8000，故本冒烟的服务器必须用 8000 端口
# 退出码 0 = 全部通过

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
$py = "$root\venv\Scripts\python.exe"
$base = "http://127.0.0.1:8000/api"
$fail = 0

function Fail($msg) { Write-Host "  [FAIL] $msg" -ForegroundColor Red; $script:fail++ }

Write-Host "== 1. manage.py check =="
Push-Location "$root\server"
& $py manage.py check 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) { Fail "check 未通过"; Pop-Location; exit 1 }
Write-Host "  [OK] check" -ForegroundColor Green

Write-Host "== 2. 单元测试（recorder/replay/asset_repo/tasksets/testdata）=="
& $py manage.py test apps.recorder apps.replay apps.asset_repo apps.tasksets apps.testdata --verbosity 1 2>&1 | Select-String "Ran |OK|FAILED"
if ($LASTEXITCODE -ne 0) { Fail "单元测试未全绿"; Pop-Location; exit 1 }
Write-Host "  [OK] tests" -ForegroundColor Green

Write-Host "== 3. 启动 dev server (:8000) =="
$server = Start-Process -FilePath $py -ArgumentList "manage.py","runserver","127.0.0.1:8000","--noreload" -WorkingDirectory "$root\server" -PassThru -WindowStyle Hidden
try {
    $ready = $false
    foreach ($i in 1..15) {
        try { Invoke-RestMethod "$base/runtimes/" -TimeoutSec 3 | Out-Null; $ready = $true; break } catch { Start-Sleep -Seconds 2 }
    }
    if (-not $ready) { throw "server 未就绪" }

    Write-Host "== 4. 演示页可访问 =="
    try { $demo = Invoke-WebRequest "http://127.0.0.1:8000/api/demo/login/" -TimeoutSec 10 -UseBasicParsing; if ($demo.StatusCode -eq 200 -and $demo.Content -match "请输入用户名") { Write-Host "  [OK] demo login page" -ForegroundColor Green } else { Fail "演示页内容异常" } } catch { Fail "演示页不可访问: $_" }

    Write-Host "== 5. 上传录制脚本并解析 =="
    $content = [System.IO.File]::ReadAllText("$root\scripts\demo_login_recorded.py", [System.Text.Encoding]::UTF8)
    $body = @{ name = "smoke-login-p1"; content = $content } | ConvertTo-Json
    $rec = Invoke-RestMethod -Method Post -Uri "$base/recordings/" -ContentType "application/json; charset=utf-8" -Body $body -TimeoutSec 30
    Write-Host ("  id=$($rec.id) start_url=$($rec.start_url) locators=$($rec.locators_count) actions=$($rec.actions_count)")
    if (-not $rec.id) { Fail "录制创建失败"; exit 1 }
    if ($rec.start_url -ne "http://127.0.0.1:8000/api/demo/login/") { Fail "start_url 解析不符: $($rec.start_url)" }
    if ($rec.actions_count -lt 5) { Fail "动作数不足: $($rec.actions_count)" }

    Write-Host "== 6. trace 回放（真实浏览器）=="
    $rp = Invoke-RestMethod -Method Post -Uri "$base/replays/" -ContentType "application/json" -Body (@{ recording_id = $rec.id } | ConvertTo-Json) -TimeoutSec 180
    Write-Host ("  status=$($rp.status) steps=$($rp.steps_passed)/$($rp.steps_total) duration=$($rp.duration_ms)ms trace=$($rp.trace_available)")
    if ($rp.status -ne "success") { Fail "回放失败: $($rp.error)" }
    if (-not $rp.trace_available) { Fail "trace 不可用" }
    if ($rp.steps_passed -lt $rp.steps_total) { Fail "存在未通过步骤" }

    Write-Host "== 7. trace 下载 =="
    $tmp = "$env:TEMP\smoke_p1_trace.zip"
    Invoke-WebRequest "$($rp.trace_url)" -OutFile $tmp -TimeoutSec 30 -UseBasicParsing
    $size = (Get-Item $tmp).Length
    Write-Host "  trace.zip = $size bytes"
    if ($size -lt 1024) { Fail "trace.zip 过小" }

    Write-Host "== 8. 元素仓 search-first：先搜 =="
    $q1 = Invoke-RestMethod -Method Post -Uri "$base/assets/elements/query/" -ContentType "application/json" -Body (@{ page_url = "http://127.0.0.1:8000/api/demo/login/"; name = "请输入用户名"; role = "textbox" } | ConvertTo-Json) -TimeoutSec 15
    Write-Host ("  confidence=$($q1.confidence) reason=$($q1.reason)")
    # 幂等断言：首轮（元素仓空）应为 none；重复运行（元素已入库）应直接 high 命中
    if ($q1.confidence -eq "none") {
        Write-Host "  [OK] 首轮未命中，符合先搜后建的 none 路径" -ForegroundColor Green
    } elseif ($q1.confidence -eq "high") {
        Write-Host "  [OK] 元素已在仓，直接 high 复用（search-first 生效）" -ForegroundColor Green
    } else {
        Fail "查询置信度异常（none/high 之外）: $($q1.confidence)"
    }

    Write-Host "== 9. 建页面对象（先搜后建）+ 新建元素 =="
    $existing = Invoke-RestMethod "$base/assets/pages/" -TimeoutSec 15
    $hit = @($existing.results | Where-Object { $_.url_pattern -eq "http://127.0.0.1:8000/api/demo/login/" })
    if ($hit.Count -gt 0) {
        $page = $hit[0]
        Write-Host "  复用已有页面 id=$($page.id)（search-first）"
    } else {
        $page = Invoke-RestMethod -Method Post -Uri "$base/assets/pages/" -ContentType "application/json" -Body (@{ name = "演示登录页"; url_pattern = "http://127.0.0.1:8000/api/demo/login/" } | ConvertTo-Json) -TimeoutSec 15
        Write-Host "  新建页面 id=$($page.id)"
    }
    $existed = Invoke-RestMethod "$base/assets/elements/?page_id=$($page.id)" -TimeoutSec 15
    $ehit = @($existed.results | Where-Object { $_.name -eq "请输入用户名" })
    if ($ehit.Count -gt 0) {
        $el = $ehit[0]
        Write-Host "  复用已有元素 id=$($el.id)（search-first）"
    } else {
        $el = Invoke-RestMethod -Method Post -Uri "$base/assets/elements/" -ContentType "application/json" -Body (@{ page_id = $page.id; name = "请输入用户名"; role = "textbox"; candidates = @(@{ type = "role"; value = 'textbox[name="请输入用户名"]'; priority = 1; robustness = "strong" }) } | ConvertTo-Json -Depth 5) -TimeoutSec 15
        Write-Host "  新建元素 id=$($el.id)"
    }

    Write-Host "== 10. 再搜（应 high 命中同一元素）=="
    $q2 = Invoke-RestMethod -Method Post -Uri "$base/assets/elements/query/" -ContentType "application/json" -Body (@{ page_url = "http://127.0.0.1:8000/api/demo/login/"; name = "请输入用户名"; role = "textbox" } | ConvertTo-Json) -TimeoutSec 15
    Write-Host ("  confidence=$($q2.confidence) match_id=$($q2.match.id)")
    if ($q2.confidence -ne "high") { Fail "二次查询应为 high，实际 $($q2.confidence)" }
    if ($q2.match.id -ne $el.id) { Fail "命中元素 id 不符" }

    Write-Host "== 11. 任务集状态机（含第二次回放）=="
    $ts = Invoke-RestMethod -Method Post -Uri "$base/tasksets/" -ContentType "application/json" -Body (@{ name = "smoke-taskset-p1"; recording_id = $rec.id } | ConvertTo-Json) -TimeoutSec 180
    Write-Host ("  status=$($ts.status) correlation=$($ts.correlation_uuid) stages=$($ts.stage_jobs.Count)")
    if ($ts.status -ne "replay_done") { Fail "任务集状态非 replay_done: $($ts.status) error=$($ts.error)" }
    if ($ts.stage_jobs.Count -lt 1 -or $ts.stage_jobs[0].stage -ne "replay" -or $ts.stage_jobs[0].status -ne "success") { Fail "StageJob(replay, success) 缺失" }
}
catch {
    Fail "未捕获异常: $($_.Exception.Message)"
}
finally {
    Write-Host "== 12. 停止 dev server =="
    if (-not $server.HasExited) { Stop-Process -Id $server.Id -Force }
    Pop-Location
}

if ($fail -gt 0) { Write-Host "`nP1 冒烟失败（$fail 项）" -ForegroundColor Red; exit 1 }
Write-Host "`nP1 冒烟全部通过" -ForegroundColor Green
