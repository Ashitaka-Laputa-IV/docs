# 运行本地服务器 (Local Server) — 速读笔记

源文件: `src/oss/langgraph/local-server.mdx`

## 核心概念

- 目标: 在本机跑起一个 **LangGraph API 服务器 (Agent Server)**, 用于开发与测试。
- `langgraph dev` 会以 **内存模式 (in-memory)** 启动 Agent Server: 无持久化后端, 只适合开发/测试。
- 生产环境请部署可访问持久化存储后端的 Agent Server。
- 服务器默认地址 `http://127.0.0.1:2024`, 同时自带 API Docs (`/docs`) 与可接入 Studio 的 UI 入口。

## 关键步骤

### 前置条件
- 一个 LangSmith API key (免费注册)。

### 1. 安装 LangGraph CLI
```bash
# Python >= 3.11 必需
pip install -U "langgraph-cli[inmem]"   # 或: uv add "langgraph-cli[inmem]"
```
```shell
# JS
npm install --save-dev @langchain/langgraph-cli
```

### 2. 创建 LangGraph 应用
- Python: 基于 `new-langgraph-project-python` 模板
  ```shell
  langgraph new path/to/your/app --template new-langgraph-project-python
  ```
  - 不指定模板会进入交互式菜单让你选。
- JS: `npm create langgraph`; 已有项目可用 `npm create langgraph config` 自动生成 `langgraph.json`。
  - config 命令会扫描 `createAgent()` / `StateGraph.compile()` / `workflow.compile()` 模式。
  - **只有已导出的 agent 才会被写入配置**; 未导出会警告, 补 `export` 即可。

### 3. 安装依赖 (edit 模式)
```bash
cd path/to/your/app
pip install -e .     # 或 uv sync
```
- **必须以 edit 模式安装**, 这样服务器才会使用你的本地改动。

### 4. 创建 `.env` 文件
- 根目录有 `.env.example`, 复制成 `.env` 并填入 key:
  ```bash
  LANGSMITH_API_KEY=lsv2...
  ```

### 5. 启动 Agent server
```shell
langgraph dev                       # Python
npx @langchain/langgraph-cli dev    # JS
```
输出会给出:
- API: `http://127.0.0.1:2024`
- Studio UI: `https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024`
- API Docs: `http://127.0.0.1:2024/docs`

### 6. 在 Studio 中测试
- 打开输出里的 Studio URL 即可可视化、交互、调试 graph。
- 自定义 host/port 时改 URL 的 `baseUrl` 查询参数 (如 `http://myhost:3000`)。
- **Safari 兼容性**: 加 `--tunnel` 标志 `langgraph dev --tunnel`, 因为 Safari 连接 localhost 受限。

### 7. 测试 API
Python SDK (sync) 示例:
```python
from langgraph_sdk import get_sync_client

client = get_sync_client(url="http://localhost:2024")

for chunk in client.runs.stream(
    None,     # Threadless run
    "agent",  # assistant 名称, 定义在 langgraph.json
    input={"messages": [{"role": "human", "content": "What is LangGraph?"}]},
    stream_mode="messages-tuple",
):
    print(f"Receiving new event of type: {chunk.event}...")
    print(chunk.data)
```
- 异步版用 `get_client` + `async for`; 也可直接用 REST (`POST http://localhost:2024/runs/stream`)。

## 心智模型

- **CLI 装包 → 模板建项目 → 装依赖 → 配 .env → `langgraph dev` 起服务 → Studio/API 验证** 是一条固定流水线。
- `langgraph dev` = 内存版 Agent Server; 它和云端部署的 API 是**同一套语义** (同样 `runs.stream`), 所以本地能跑通, 云端部署基本无痛。
- 三个入口同源: 同一个服务器同时暴露 **API `/docs`**、**Studio UI**、**SDK 端点**。

## 易错点 / 注意事项

- **Python >= 3.11 是硬要求** (安装 CLI 时注释明确)。
- **依赖必须 edit 模式安装** (`pip install -e .` / `uv sync`), 否则改动不生效。
- **`--tunnel` 只在 Safari 场景需要**, 但用了之后需要把隧道 URL 加到允许来源 (Studio 里点 "Connect to a local server")。
- 默认端口 **2024**, 客户端 `url` 要与之匹配; 改端口时 Studio 的 `baseUrl` 也要跟着改。
- `stream_mode` 用 `messages-tuple` (sync 示例) 才能拿到逐 token/逐消息的结构; 用错模式事件结构会不符预期。
- 内存服务器**不持久化**, 进程退出数据即丢; 不要用于生产。
