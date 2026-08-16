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

# 2. Django AgentGateway 调用形态（P2 已实现）
$env:DSH_HOME = "D:\AI-soft\AI-TESTHUB\DSH-Ops\agent\home"
& "D:\AI-soft\AI-TESTHUB\DSH-Ops\agent\runtime\node_modules\.bin\dsh.cmd" `
    --profile headless "<阶段指令>"
```

### headless 输出语义（2025-12 实测验证）

平台以 subprocess 调用并按以下语义解析（探针：`--profile headless "只回复两个字符: OK"`
-> exit 0 / stdout=`OK` / stderr 空 / 53s）：

| 信号 | 语义 |
|---|---|
| stdout | **最后一条非空 assistant 文本** = 阶段最终回答（AgentGateway 从中提取 JSON） |
| stderr | 成功时为空；终态 error 时含 code+message |
| 退出码 | 0 = turn 正常完成；1 = 未完成/出错 |

注意事项：
- 单轮小指令约 50~60s；A1/A2 阶段预算 1~3 分钟，网关超时默认 300s
  （env `DSHOPS_AGENT_TIMEOUT`）。
- 工作区用 subprocess 的 `cwd` 参数指定（无需 --cwd 标志）。
- 凭据默认继承用户全局 `~/.dsh`；隔离模式设 `DSHOPS_AGENT_HOME`
  （此时该 home 需自行配置模型凭据）。
- headless profile 首次使用会从随附模板自动初始化（无需 dsh plugin）。

## 隔离原则（为什么要有第二套）

平台实例与开发者个人 `~/.dsh` 完全隔离：凭据独立、配置独立、会话审计独立、
版本独立锁死。个人全局 dsh 升级不影响平台；`npm update` 永远不要在 `runtime/` 里盲跑。

## testhub profile（P3 计划）

P2 直接用自动初始化的 `headless` profile（零配置即可跑）。P3 再经 `dsh plugin` 创建
`testhub` profile：挂载 `skills/` 目录 + MCP client 指向平台 MCP server
（`manage.py run_mcp_server`），让 A4/A5 生成阶段可在智能体内直接查元素仓。
