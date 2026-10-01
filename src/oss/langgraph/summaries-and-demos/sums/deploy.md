# 部署 (Deploy) — 速读笔记

源文件: `src/oss/langgraph/deploy.mdx`

## 核心概念

- 把本地可运行的 LangGraph agent 变成生产环境里的**托管服务**, 由平台负责基础设施、扩缩容与运维。
- 首选方案是 **LangSmith Cloud**: 面向有状态、长时运行的 agent, 提供全托管基础设施 + 持久 state + 后台执行能力。
- 部署的输入是一个 **GitHub 仓库** (代码不在 GitHub 上就无法部署)。
- 除 Cloud 外还有: hybrid、standalone servers、self-hosted with control plane (详见 LangSmith Deployment 概览)。

## 关键步骤 (部署到 LangSmith Cloud)

### 前置条件
- 一个 GitHub 账号
- 一个 LangSmith 账号 (免费注册)

### 1. 在 GitHub 上创建仓库
- 应用代码必须位于 GitHub 仓库 (公有/私有均可)。
- 先按本地服务器指南确认应用与 LangGraph 兼容, 再把代码 push 上去。

### 2. 部署到 LangSmith
1. 登录 LangSmith, 左侧边栏选 **Deployments**。
2. 点击 **+ New Deployment**。
3. 首次或连接未用过的私有仓库时, 点 **Add new account** 连接 GitHub。
4. 选择仓库 → **Submit** 部署。耗时约 15 分钟。在 **Deployment details** 里看状态。

### 3. 在 Studio 中测试应用
- 选中刚创建的部署 → 点右上角 **Studio** 按钮 → 打开并显示你的 graph。

### 4. 获取部署的 API URL
- 在 **Deployment details** 视图里点 **API URL** 复制。

### 5. 测试 API
Python (官方示例):
```shell
pip install langgraph-sdk
```
```python
from langgraph_sdk import get_sync_client  # 或 get_client 走异步

client = get_sync_client(url="your-deployment-url", api_key="your-langsmith-api-key")

for chunk in client.runs.stream(
    None,     # Threadless run (无 thread 的一次性运行)
    "agent",  # agent 名称, 定义在 langgraph.json 里
    input={"messages": [{"role": "human", "content": "What is LangGraph?"}]},
    stream_mode="updates",
):
    print(f"Receiving new event of type: {chunk.event}...")
    print(chunk.data)
```
- TS 用 `@langchain/langgraph-sdk` 的 `Client`, REST 用 `POST /runs/stream`, 语义一致。

## 心智模型

- **代码托管 (GitHub) → 部署 (LangSmith Cloud) → 服务端点 (API URL) → 客户端 SDK 调用** 是完整链路。
- 部署后的 agent 本质是一个 **Agent Server** 端点, 所有客户端 (SDK / REST / Studio / Agent Chat UI) 都打同一个 `runs/stream` 类接口。
- `assistant_id` / graph 名 `"agent"` 来自 `langgraph.json` 的 `graphs` 键, 不是随便起的名字。
- `Threadless run` (第一参数传 `None`) = 不关联 thread 的单次执行; 需要多轮记忆时才传 thread_id。

## 易错点 / 注意事项

- **必须先在 GitHub 建仓库**: 没有仓库就无法进入部署流程。
- **部署耗时较长 (约 15 分钟)**, 别以为卡住了; 到 Deployment details 查看进度。
- **私有仓库首次需授权 GitHub 账号** (Add new account), 否则列表里看不到仓库。
- `stream_mode` 取值不同 (如 `updates` / `messages` / `messages-tuple`) 返回的 `chunk.data` 结构不同, 客户端解析逻辑要匹配。
- **API key 与 URL 配套**: `url` 用部署的 API URL, `api_key` 用 LangSmith API key。
- 生产环境不要用本地 `langgraph dev` 的内存模式; 那只是开发/测试用。详见本地服务器笔记。
