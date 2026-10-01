# LangSmith Studio — 速读笔记

源文件: `src/oss/langgraph/studio.mdx`

## 核心概念

- **Studio 是一个免费的可视化界面**, 用于在本地开发/测试 LangChain agent。
- 它连接你本地运行的 agent, 展示 agent 所采取的每一步: 送往 model 的 prompt、tool call 及其结果、最终输出。
- 无需额外代码或部署即可: 测试不同输入、检查中间 state、迭代 agent 行为。
- Studio 依赖一个在本地跑的 **Agent Server** (由 LangGraph CLI 提供), 由它把 agent 接到 Studio。

## 关键步骤

### 前置条件
- 一个 LangSmith 账号 (smith.langchain.com 免费注册)。
- 一个 LangSmith API key。
- 若不希望数据被追踪到 LangSmith, 在 `.env` 设 `LANGSMITH_TRACING=false`; 禁用后无数据离开本地服务器。

### 1. 安装 LangGraph CLI
```shell
# Python >= 3.11
pip install --upgrade "langgraph-cli[inmem]"
```
```shell
# JS
npx @langchain/langgraph-cli
```

### 2. 准备你的 agent
官方示例 (email agent):
```python
from langchain.agents import create_agent

def send_email(to: str, subject: str, body: str):
    """Send an email"""
    email = {"to": to, "subject": subject, "body": body}
    # ... email sending logic
    return f"Email sent to {to}"

agent = create_agent(
    "gpt-5.5",
    tools=[send_email],
    system_prompt="You are an email assistant. Always use the send_email tool.",
)
```

### 3. 环境变量
- 项目根目录创建 `.env`:
  ```bash
  LANGSMITH_API_KEY=lsv2...
  ```
- **确保 `.env` 不被提交到 Git。**

### 4. 创建 LangGraph 配置文件
- 应用目录建 `langgraph.json`:
  ```json
  {
    "dependencies": ["."],
    "graphs": { "agent": "./src/agent.py:agent" },
    "env": ".env"
  }
  ```
- 关键点: `create_agent` 会自动返回一个**已编译的 LangGraph graph**, 正是 `graphs` 键期望的值。
- 项目结构:
  ```
  my-app/
  ├── src/agent.py
  ├── .env
  └── langgraph.json
  ```

### 5. 安装依赖
```shell
pip install langchain langchain-openai   # 或 uv add ...
```

### 6. 在 Studio 中查看你的 agent
```shell
langgraph dev
```
- 服务器运行后: API 在 `http://127.0.0.1:2024`, Studio UI 在 `https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024`。
- **Safari 会阻止到 Studio 的 localhost 连接**: 用 `--tunnel` 运行, 并手动把隧道 URL 加到允许来源 (Studio 里点 **Connect to a local server**)。

### Studio 提供的能力
- 运行测试输入 → 检查完整执行 trace (prompt、tool 参数、返回值、token/延迟指标)。
- 出错时连同周围 state 一起捕获异常。
- **热重载**: 改 prompt 或 tool 签名, Studio 立即反映。
- 可从任意步骤**重新运行 thread**, 无需从头开始。
- 单 tool agent 与复杂多 node graph 都适用。

## 心智模型

- Studio = **本地 agent 的可视化调试器**, 它与 agent 之间隔着一个 Agent Server (LangGraph CLI 提供)。
- `create_agent` 的返回值 (compiled graph) 与 `langgraph.json` 的 `graphs` 映射一一对应 —— 这也是为什么配置里写 `"./src/agent.py:agent"`。
- **代码改 → 热重载 → Studio 立即可见** 是它的核心工作循环。

## 易错点 / 注意事项

- **`.env` 绝不能进版本控制** (含 API key)。
- **Safari 需要 `--tunnel`**, 且要手动配置允许来源, 否则连不上。
- `langgraph.json` 的路径要指向**导出的对象** (`模块:变量名`), 变量名必须与代码里一致 (示例是 `agent`)。
- `LANGSMITH_TRACING=false` 是"完全不外发数据"的开关, 需要隐私时用它; 但代价是失去 LangSmith 里的 trace 能力。
- Studio 是**免费本地开发工具**, 不是部署产品; 云端部署后的 Studio 入口在 Deployment details 里 (见部署笔记)。
