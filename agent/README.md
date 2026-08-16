# agent/ —— DSH 侧资产（源码零改动原则）

平台对 DeepSeek Harness 的使用方式：**npm 局部安装 + 独立 DSH_HOME + profile/skills/MCP 扩展**，
绝不 fork、不改 DSH 源码。

## 目录

```
agent/
├── runtime/          # 平台专用 dsh 安装（package.json 锁版本；node_modules/ 不入库）
│   └── package.json  #   锁 @deepseek-ai/dsh@0.1.0-rc.6，升级=显式改这里+冒烟测试
├── home/             # 平台专用 DSH_HOME（凭据/会话/profiles；整个目录不入库）
└── skills/           # agent 技能（入库，随仓库分发）
    ├── tester.md         # 用例设计师人设（A2，自旧平台 backend/docs 移植）
    ├── tester_pro.md     # 用例评审员人设（A3，自旧平台移植）
    └── pom-extraction/   # A1 提取技能说明
```

## 安装与调用

```powershell
# 1. 安装平台运行时（一次性）
cd D:\AI-soft\AI-TESTHUB\DSH-Ops\agent\runtime
npm install

# 2. Django AgentGateway 调用形态（P2 实现，先在此记录约定）
$env:DSH_HOME = "D:\AI-soft\AI-TESTHUB\DSH-Ops\agent\home"
& "D:\AI-soft\AI-TESTHUB\DSH-Ops\agent\runtime\node_modules\.bin\dsh.cmd" `
    --profile testhub --cwd <workspace> headless "<阶段指令>"
```

## 隔离原则（为什么要有第二套）

平台实例与开发者个人 `~/.dsh` 完全隔离：凭据独立、配置独立、会话审计独立、
版本独立锁死。个人全局 dsh 升级不影响平台；`npm update` 永远不要在 `runtime/` 里盲跑。

## testhub profile（P2 初始化）

`dsh plugin --profile testhub` 创建，内容：minimal preset + `skills/` 挂载 +
MCP client 指向 TestHub MCP server。初始化步骤在 P2 的 SKILL.md 里补全。
