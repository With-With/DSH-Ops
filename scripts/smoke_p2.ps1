# P2 集成冒烟：任务集 -> A1 提取(mock) -> 元素并入 -> A2 设计(mock) -> 草案评审 全链
# 用法: powershell -ExecutionPolicy Bypass -File scripts\smoke_p2.ps1
# 默认 DSHOPS_AGENT_MODE=mock（不调真实 LLM）；加 -Real 参数走真实 DSH（耗时/耗 token，手动用）
# 退出码 0 = 全部通过
#
# 坑（P2 实测）：PowerShell 5.1 的 Invoke-RestMethod 字符串体按 GBK 发送，
# 中文会乱码——所有 POST 统一用 UTF-8 字节体（PostJson 辅助函数）。

param([switch]$Real)

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
$py = "$root\venv\Scripts\python.exe"
$base = "http://127.0.0.1:8001/api"
$fail = 0

function Fail($msg) { Write-Host "  [FAIL] $msg" -ForegroundColor Red; $script:fail++ }

function PostJson($uri, $obj, [int]$timeout = 30) {
    $json = $obj | ConvertTo-Json -Depth 8
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($json)
    return Invoke-RestMethod -Method Post -Uri $uri -ContentType "application/json; charset=utf-8" -Body $bytes -TimeoutSec $timeout
}

Write-Host "== 1. manage.py check =="
Push-Location "$root\server"
& $py manage.py check 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) { Fail "check 未通过"; Pop-Location; exit 1 }
Write-Host "  [OK] check" -ForegroundColor Green

Write-Host "== 2. 单元测试（全 app）=="
& $py manage.py test apps --verbosity 1 2>&1 | Select-String "Ran |OK|FAILED"
if ($LASTEXITCODE -ne 0) { Fail "单元测试未全绿"; Pop-Location; exit 1 }
Write-Host "  [OK] tests" -ForegroundColor Green

Write-Host "== 3. 启动 dev server (:8000, $(if ($Real) { "REAL" } else { "MOCK" }) 模式) =="
$env:DSHOPS_AGENT_MODE = $(if ($Real) { "real" } else { "mock" })
$server = Start-Process -FilePath $py -ArgumentList "manage.py","runserver","127.0.0.1:8001","--noreload" -WorkingDirectory "$root\server" -PassThru -WindowStyle Hidden
try {
    $ready = $false
    foreach ($i in 1..15) {
        try { Invoke-RestMethod "$base/runtimes/" -TimeoutSec 3 | Out-Null; $ready = $true; break } catch { Start-Sleep -Seconds 2 }
    }
    if (-not $ready) { throw "server 未就绪" }

    Write-Host "== 4. 上传录制并建任务集（同步回放）=="
    $content = [System.IO.File]::ReadAllText("$root\scripts\demo_login_recorded.py", [System.Text.Encoding]::UTF8)
    $rec = PostJson "$base/recordings/" @{ name = "smoke-p2"; content = $content } 30
    $ts = PostJson "$base/tasksets/" @{ name = "smoke-p2-taskset"; recording_id = $rec.id } 180
    Write-Host ("  taskset=$($ts.id) status=$($ts.status)")
    if ($ts.status -ne "replay_done") { Fail "任务集回放阶段未通过: $($ts.status) $($ts.error)" }

    Write-Host "== 5. A1 提取阶段（异步 202 + 轮询）=="
    $r1 = PostJson "$base/tasksets/$($ts.id)/stages/" @{ stage = "extract" } 30
    Write-Host ("  POST -> status=$($r1.status) current_stage=$($r1.current_stage)")
    if ($r1.status -ne "extracting") { Fail "extract 未被接受: $($r1.status)" }
    $deadline = (Get-Date).AddSeconds($(if ($Real) { 360 } else { 90 }))
    do {
        Start-Sleep -Seconds 3
        $ts = Invoke-RestMethod "$base/tasksets/$($ts.id)/" -TimeoutSec 15
        Write-Host "    轮询: $($ts.status)"
        if ((Get-Date) -gt $deadline) { Fail "extract 超时"; break }
    } while ($ts.status -eq "extracting")
    if ($ts.status -ne "extract_done") { Fail "A1 提取未成功: $($ts.status)" }

    Write-Host "== 6. POM 草案 + 元素并入断言 =="
    $pomDrafts = Invoke-RestMethod "$base/reviews/drafts/?kind=pom" -TimeoutSec 15
    $pom = @($pomDrafts.results | Where-Object { $_.task_set_id -eq $ts.id })[0]
    if (-not $pom) { Fail "POM 草案缺失" } else {
        Write-Host ("  pom draft=$($pom.id) valid=$($pom.valid) status=$($pom.status) elements=$($pom.content.elements.Count)")
        if (-not $pom.valid) { Fail "POM 草案校验未通过: $($pom.validation_errors -join '; ')" }
        if ($pom.content.elements.Count -lt 3) { Fail "POM 元素数不足" }
    }
    $q = PostJson "$base/assets/elements/query/" @{ page_url = "http://127.0.0.1:8001/api/demo/login/"; name = "登录"; role = "button" } 15
    Write-Host ("  search-first 查【登录】按钮: confidence=$($q.confidence)")
    if ($q.confidence -ne "high") { Fail "A1 并入后登录按钮应 high 命中: $($q.confidence) reason=$($q.reason)" }

    Write-Host "== 7. A2 设计阶段（异步 202 + 轮询）=="
    $r2 = PostJson "$base/tasksets/$($ts.id)/stages/" @{ stage = "design" } 30
    if ($r2.status -ne "designing") { Fail "design 未被接受: $($r2.status)" }
    $deadline = (Get-Date).AddSeconds($(if ($Real) { 360 } else { 90 }))
    do {
        Start-Sleep -Seconds 3
        $ts = Invoke-RestMethod "$base/tasksets/$($ts.id)/" -TimeoutSec 15
        Write-Host "    轮询: $($ts.status)"
        if ((Get-Date) -gt $deadline) { Fail "design 超时"; break }
    } while ($ts.status -eq "designing")
    if ($ts.status -ne "design_done") { Fail "A2 设计未成功: $($ts.status)" }

    Write-Host "== 8. matrix 草案断言 =="
    $mDrafts = Invoke-RestMethod "$base/reviews/drafts/?kind=matrix" -TimeoutSec 15
    $mat = @($mDrafts.results | Where-Object { $_.task_set_id -eq $ts.id })[0]
    if (-not $mat) { Fail "matrix 草案缺失" } else {
        Write-Host ("  matrix draft=$($mat.id) valid=$($mat.valid)")
        if (-not $mat.valid) { Fail "matrix 草案校验未通过: $($mat.validation_errors -join '; ')" }
    }

    Write-Host "== 9. 评审：驳回后重评被拒 =="
    if ($pom) {
        try {
            PostJson "$base/reviews/drafts/$($pom.id)/reject/" @{ note = "冒烟驳回测试" } 15 | Out-Null
            $pomList = Invoke-RestMethod "$base/reviews/drafts/?kind=pom" -TimeoutSec 15
            $pom2 = @($pomList.results | Where-Object { $_.id -eq $pom.id })[0]
            if ($pom2.status -ne "rejected") { Fail "驳回未生效: $($pom2.status)" }
            try {
                PostJson "$base/reviews/drafts/$($pom.id)/approve/" @{ note = "重审通过" } 15 | Out-Null
                Fail "已 rejected 的草案再 approve 应 409"
            } catch { Write-Host "  [OK] 重复评审被拒(409)" -ForegroundColor Green }
            Write-Host "  [OK] 评审流转 rejected + 409" -ForegroundColor Green
        } catch { Fail "评审接口异常: $_" }
    }

    Write-Host "== 10. 回放可选异步 =="
    $rp = PostJson "$base/replays/?async=1" @{ recording_id = $rec.id } 30
    Write-Host ("  async POST -> id=$($rp.id) status=$($rp.status)")
    if ($rp.status -ne "running") { Fail "async 回放应立即返回 running: $($rp.status)" }
    $deadline = (Get-Date).AddSeconds(120)
    do {
        Start-Sleep -Seconds 2
        $rp = Invoke-RestMethod "$base/replays/$($rp.id)/" -TimeoutSec 15
        if ((Get-Date) -gt $deadline) { Fail "async 回放超时"; break }
    } while ($rp.status -eq "running")
    Write-Host "  终态: $($rp.status) ($($rp.steps_passed)/$($rp.steps_total))"
    if ($rp.status -ne "success") { Fail "async 回放未成功: $($rp.error)" }
}
catch {
    Fail "未捕获异常: $($_.Exception.Message)"
}
finally {
    Write-Host "== 11. 停止 dev server =="
    if (-not $server.HasExited) { Stop-Process -Id $server.Id -Force }
    Pop-Location
}

if ($fail -gt 0) { Write-Host "`nP2 冒烟失败（$fail 项）" -ForegroundColor Red; exit 1 }
Write-Host "`nP2 冒烟全部通过（$(if ($Real) { "真实 DSH" } else { "mock" })模式）" -ForegroundColor Green
