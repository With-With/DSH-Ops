# P3 集成冒烟：任务集一键流水线（replay->extract->design->review->generate）全链
# 用法: powershell -ExecutionPolicy Bypass -File scripts\smoke_p3.ps1
# 默认 mock（不调真实 LLM）；加 -Real 走真实 DSH（每阶段 1-2 分钟，全链约 6-10 分钟）
# 退出码 0 = 全部通过

param([switch]$Real)

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
$py = "$root\venv\Scripts\python.exe"
$base = "http://127.0.0.1:8000/api"
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
$server = Start-Process -FilePath $py -ArgumentList "manage.py","runserver","127.0.0.1:8000","--noreload" -WorkingDirectory "$root\server" -PassThru -WindowStyle Hidden
try {
    $ready = $false
    foreach ($i in 1..15) {
        try { Invoke-RestMethod "$base/runtimes/" -TimeoutSec 3 | Out-Null; $ready = $true; break } catch { Start-Sleep -Seconds 2 }
    }
    if (-not $ready) { throw "server 未就绪" }

    Write-Host "== 4. 上传录制 =="
    $content = [System.IO.File]::ReadAllText("$root\scripts\demo_login_recorded.py", [System.Text.Encoding]::UTF8)
    $rec = PostJson "$base/recordings/" @{ name = "smoke-p3"; content = $content } 30
    Write-Host "  recording=$($rec.id)"

    Write-Host "== 5. 一键流水线（异步 202 + 轮询）=="
    $ts = PostJson "$base/tasksets/" @{ name = "smoke-p3-taskset"; recording_id = $rec.id } 180
    Write-Host "  任务集=$($ts.id) 初始=$($ts.status)"
    $r = PostJson "$base/tasksets/$($ts.id)/pipeline/" @{} 30
    Write-Host ("  pipeline POST -> 202, current_stage=$($r.current_stage)")
    $deadline = (Get-Date).AddSeconds($(if ($Real) { 1500 } else { 120 }))
    do {
        Start-Sleep -Seconds 3
        $ts = Invoke-RestMethod "$base/tasksets/$($ts.id)/" -TimeoutSec 15
        if ($ts.status -ne "generate_done" -and $ts.status -ne "failed") {
            Write-Host "    轮询: $($ts.status)"
        }
        if ((Get-Date) -gt $deadline) { Fail "流水线超时（最后状态 $($ts.status)）"; break }
    } while ($ts.status -notin @("generate_done", "failed"))
    Write-Host "  终态: $($ts.status)"
    if ($ts.status -ne "generate_done") { Fail "流水线未到 generate_done: $($ts.status) error=$($ts.error)" }

    Write-Host "== 6. 五阶段 StageJob 断言 =="
    $stages = @($ts.stage_jobs | ForEach-Object { $_.stage })
    $stageSummary = ($ts.stage_jobs | ForEach-Object { "$($_.stage):$($_.status)" }) -join " "
    Write-Host "  $stageSummary"
    foreach ($s in @("replay", "extract", "design", "review", "generate")) {
        if ($s -notin $stages) { Fail "缺少 $s 阶段作业" }
    }
    foreach ($j in $ts.stage_jobs) {
        if ($j.status -ne "success") { Fail "阶段 $($j.stage) 未成功: $($j.status)" }
    }

    Write-Host "== 7. 产物断言（草案/评审/生成脚本）=="
    $pomD = @($ts.drafts | Where-Object { $_.kind -eq "pom" })[0]
    $revD = @($ts.drafts | Where-Object { $_.kind -eq "review" })[0]
    $gen = @($ts.generated)[0]
    if (-not $pomD) { Fail "POM 草案缺失" }
    if (-not $revD) { Fail "A3 评审报告缺失" }
    Write-Host ("  drafts: pom=$($pomD.valid) review=$($revD.valid)")
    if ($gen) {
        Write-Host ("  generated: $($gen.script_file) status=$($gen.status) rounds=$($gen.rounds) script_len=$($gen.script_content.Length)")
        if ($gen.status -ne "pass") { Fail "生成脚本未通过: $($gen.status)" }
        if ($gen.script_content.Length -lt 200) { Fail "脚本内容过短（未含真实代码）" }
    } else { Fail "生成产物缺失" }

    Write-Host "== 8. 观测中心 =="
    $ov = Invoke-RestMethod "$base/obs/overview/" -TimeoutSec 15
    Write-Host ("  invocations=$($ov.invocations.total) replays=$($ov.replays.total) stages=$($ov.stages.total) generated=$($ov.generated.total) pass_rate=$($ov.generated.pass_rate)%")
    if ($ov.generated.total -lt 1) { Fail "观测中心 generated 计数异常" }
    $act = Invoke-RestMethod "$base/obs/activity/?limit=20" -TimeoutSec 15
    Write-Host ("  activity 事件数: $($act.results.Count)")
    if ($act.results.Count -lt 1) { Fail "观测中心活动流为空" }
}
catch {
    Fail "未捕获异常: $($_.Exception.Message)"
}
finally {
    Write-Host "== 9. 停止 dev server =="
    if (-not $server.HasExited) { Stop-Process -Id $server.Id -Force }
    Pop-Location
}

if ($fail -gt 0) { Write-Host "`nP3 冒烟失败（$fail 项）" -ForegroundColor Red; exit 1 }
Write-Host "`nP3 冒烟全部通过（$(if ($Real) { "真实 DSH" } else { "mock" })模式）" -ForegroundColor Green
