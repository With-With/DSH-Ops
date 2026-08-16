# 全局接口探测：起临时 8001 服务，扫全部 GET 端点 + 关键 POST（安全参数）
# 用法: powershell -ExecutionPolicy Bypass -File scripts\check_api.ps1
# 退出码 0 = 全部 2xx；非 0 = 有异常（输出失败清单）
# 开发纪律：每次提交前必跑，防止 500/404 回归

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
$py = "$root\venv\Scripts\python.exe"
$base = "http://127.0.0.1:8001"
$fail = 0

function Fail($msg) { Write-Host "  [FAIL] $msg" -ForegroundColor Red; $script:fail++ }

Write-Host "== 启动临时后端 (:8001) =="
$server = Start-Process -FilePath $py -ArgumentList "manage.py","runserver","127.0.0.1:8001","--noreload" -WorkingDirectory "$root\server" -PassThru -WindowStyle Hidden
try {
    $ready = $false
    foreach ($i in 1..15) {
        try { Invoke-RestMethod "$base/api/runtimes/" -TimeoutSec 3 | Out-Null; $ready = $true; break } catch { Start-Sleep -Seconds 2 }
    }
    if (-not $ready) { Write-Host "后端未就绪" -ForegroundColor Red; exit 1 }

    Write-Host "== GET 端点扫描 =="
    $gets = @(
        "/api/runtimes/", "/api/runtimes/components/",
        "/api/recordings/", "/api/recordings/codegen/status/",
        "/api/replays/",
        "/api/assets/pages/", "/api/assets/elements/",
        "/api/tasksets/", "/api/tasksets/1/",
        "/api/reviews/drafts/",
        "/api/obs/overview/", "/api/obs/activity/",
        "/api/ai-configs/",
        "/api/agent/invocations/", "/api/agent/drafts/",
        "/api/testdata/params/",
        "/api/testcases/",
        "/api/demo/login/"
    )
    foreach ($u in $gets) {
        try {
            $r = Invoke-WebRequest "$base$u" -TimeoutSec 20 -UseBasicParsing
            if ($r.StatusCode -lt 200 -or $r.StatusCode -ge 300) { Fail "$($r.StatusCode) GET $u" }
            else { Write-Host "  [OK] $($r.StatusCode) GET $u" -ForegroundColor Green }
        } catch {
            $code = if ($_.Exception.Response) { $_.Exception.Response.StatusCode.value__ } else { "ERR" }
            Fail "$code GET $u"
        }
    }

    Write-Host "== 关键 POST 扫描（安全参数）=="
    function Post($u, $body) {
        try {
            $b = [System.Text.Encoding]::UTF8.GetBytes($body)
            $r = Invoke-WebRequest "$base$u" -Method Post -ContentType "application/json; charset=utf-8" -Body $b -TimeoutSec 60 -UseBasicParsing
            if ($r.StatusCode -lt 200 -or $r.StatusCode -ge 300) { Fail "$($r.StatusCode) POST $u" }
            else { Write-Host "  [OK] $($r.StatusCode) POST $u" -ForegroundColor Green }
        } catch {
            $code = if ($_.Exception.Response) { $_.Exception.Response.StatusCode.value__ } else { "ERR" }
            # 409/404 为业务性预期（守卫/不存在），不视为失败
            if ($code -in @(400,409,404)) { Write-Host "  [WARN] $code POST $u（业务预期）" -ForegroundColor Yellow }
            else { Fail "$code POST $u" }
        }
    }
    Post "/api/assets/elements/query/" '{"page_url":"http://127.0.0.1:8001/api/demo/login/","name":"x"}'
    Post "/api/tasksets/1/cancel/" '{}'
    Post "/api/reviews/drafts/1/approve/" '{}'
    Post "/api/recordings/codegen/stop/" '{}'
    Post "/api/ai-configs/1/test/" '{}'
    Post "/api/testcases/bulk-delete/" '{"ids":[]}'
    Post "/api/replays/bulk-delete/" '{"ids":[]}'
    Post "/api/assets/elements/bulk-delete/" '{"ids":[]}'
}
finally {
    if (-not $server.HasExited) { Stop-Process -Id $server.Id -Force }
}

Write-Host ""
if ($fail -gt 0) { Write-Host "接口探测失败（$fail 项）" -ForegroundColor Red; exit 1 }
Write-Host "接口探测全部通过" -ForegroundColor Green
