from django.http import HttpResponse
from django.views import View


DEMO_LOGIN_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>DSH-Ops 演示登录</title>
    <style>
        body {
            font-family: system-ui, -apple-system, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            background: #f5f7fa;
        }
        .login-box {
            background: #fff;
            padding: 32px 40px;
            border-radius: 8px;
            box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
            width: 360px;
        }
        .login-box h2 {
            margin: 0 0 24px 0;
            text-align: center;
            color: #303133;
        }
        .form-item {
            margin-bottom: 16px;
        }
        .form-item input {
            width: 100%;
            padding: 10px 12px;
            border: 1px solid #dcdfe6;
            border-radius: 4px;
            font-size: 14px;
            box-sizing: border-box;
        }
        .form-item input:focus {
            outline: none;
            border-color: #409eff;
        }
        .login-btn {
            width: 100%;
            padding: 10px;
            background: #409eff;
            color: #fff;
            border: none;
            border-radius: 4px;
            font-size: 14px;
            cursor: pointer;
        }
        .login-btn:hover {
            background: #66b1ff;
        }
        #welcome {
            margin-top: 16px;
            padding: 12px;
            text-align: center;
            color: #67c23a;
            background: #f0f9eb;
            border-radius: 4px;
            display: none;
        }
        #error-msg {
            margin-top: 12px;
            padding: 10px 12px;
            text-align: center;
            color: #f56c6c;
            background: #fef0f0;
            border-radius: 4px;
            display: none;
            font-size: 13px;
        }
    </style>
</head>
<body>
    <div class="login-box">
        <h2>DSH-Ops 演示登录</h2>
        <form id="login-form" onsubmit="return handleLogin(event)">
            <div class="form-item">
                <input
                    type="text"
                    role="textbox"
                    aria-label="请输入用户名"
                    placeholder="请输入用户名"
                    id="username"
                    autocomplete="username"
                >
            </div>
            <div class="form-item">
                <input
                    type="password"
                    placeholder="请输入密码"
                    id="password"
                    aria-label="请输入密码"
                    autocomplete="current-password"
                >
            </div>
            <button type="submit" role="button" class="login-btn">登录</button>
        </form>
        <div id="error-msg"></div>
        <div id="welcome"></div>
    </div>
    <script>
        function handleLogin(event) {
            event.preventDefault();
            var username = document.getElementById('username').value;
            var password = document.getElementById('password').value;
            var welcomeEl = document.getElementById('welcome');
            var errorEl = document.getElementById('error-msg');
            welcomeEl.style.display = 'none';
            errorEl.style.display = 'none';
            if (!username || !username.trim()) {
                errorEl.textContent = '请输入用户名';
                errorEl.style.display = 'block';
                return false;
            }
            if (!password) {
                errorEl.textContent = '请输入密码';
                errorEl.style.display = 'block';
                return false;
            }
            if (password !== 'admin123456') {
                errorEl.textContent = '用户名或密码错误';
                errorEl.style.display = 'block';
                return false;
            }
            welcomeEl.textContent = '欢迎回来，' + username;
            welcomeEl.style.display = 'block';
            return false;
        }
    </script>
</body>
</html>
"""


class DemoLoginView(View):
    """演示登录页：供回放冒烟测试使用，允许 GET 无鉴权。"""

    def get(self, request):
        return HttpResponse(DEMO_LOGIN_HTML, content_type="text/html; charset=utf-8")
