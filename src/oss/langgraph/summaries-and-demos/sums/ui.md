# Agent Chat UI — 速读笔记

源文件: `src/oss/langgraph/ui.mdx`

## 核心概念

- **Agent Chat UI** 是一个 **Next.js 应用**, 为任意 LangChain agent 提供对话式界面。
- 支持: 实时聊天、tool 可视化、以及时间旅行调试 (time-travel) 与 state 分叉 (state forking) 等高级功能。
- 与 `create_agent` 创建的 agent 无缝配合, 本地运行或已部署 (如 LangSmith) 都能用, 最小配置。
- 开源, 可按需改造。
- 也可在其上使用生成式 UI (generative UI)。

## 关键步骤

### 快速开始 (托管版, 最快)
1. 访问 [Agent Chat UI](https://agentchat.vercel.app)。
2. 输入你的部署 URL 或本地服务器地址以连接 agent。
3. 开始聊天 —— UI 会自动检测并渲染 tool call 与中断 (interrupts)。

### 本地开发 (定制)
```bash
# 方式一: npx 脚手架
npx create-agent-chat-app --project-name my-chat-ui
cd my-chat-ui
pnpm install
pnpm dev
```
```bash
# 方式二: 克隆仓库
git clone https://github.com/langchain-ai/agent-chat-ui.git
cd agent-chat-ui
pnpm install
pnpm dev
```

### 连接到你的 agent
Agent Chat UI 既能连 [本地 agent](/oss/langgraph/studio#set-up-local-agent-server), 也能连 [已部署的 agent](/oss/langgraph/deploy)。启动后需配置:
1. **Graph ID**: 你的 graph 名称 (在 `langgraph.json` 的 `graphs` 下找)。
2. **Deployment URL**: Agent server 端点 (本地开发如 `http://localhost:2024`, 或已部署 agent 的 URL)。
3. **LangSmith API key (optional)**: 添加 LangSmith API key; **本地 Agent server 无需填写**。

配置完成后, Agent Chat UI 会自动拉取并显示 agent 中所有**被中断的 thread**。

## 心智模型

- Agent Chat UI 是 agent 的**前端外壳**; 它不关心 agent 内部实现, 只通过 Agent Server 的协议 (Graph ID + Deployment URL) 通信。
- **同一套 UI 同时适配本地与云端**: 差别只在填的 Deployment URL。
- 它把 agent 的能力"可视化"出来: tool call、tool 结果、interrupt 的 thread 都能开箱渲染。

## 易错点 / 注意事项

- **Graph ID 必须与 `langgraph.json` 的 `graphs` 键一致**, 否则找不到图。
- **Deployment URL 要指向 Agent server 端点**, 不是 Studio 的 URL。
- **本地 Agent server 不需要填 LangSmith API key** (该字段是 optional, 主要给云端/需要鉴权的场景)。
- 开箱支持渲染 tool call 与 tool 结果消息; 要自定义显示哪些消息, 见官方 "在聊天中隐藏消息" 说明。
- 本页是纯 UI/前端章节, **没有可独立运行的 Python demo**; 运行前需要先有可访问的 agent server (见本地服务器笔记)。
