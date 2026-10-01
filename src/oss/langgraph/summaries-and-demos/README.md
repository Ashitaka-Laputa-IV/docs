# LangGraph 教程速读笔记与 Demo 索引

本目录是对 `src/oss/langgraph/` 下**已翻译为中文的章节**（共 23 篇）所做的结构化速读笔记与可运行 demo 的汇总索引。

- 生成规范见 [`AGENTS.md`](./AGENTS.md)：源文件为 `.mdx`，笔记为**纯 Markdown**（严禁 MDX / Mintlify 语法），demo 为最小可运行的 Python。
- 同一批章节的 **Jupyter Notebook 版本**见 [`../ipynbs/`](../ipynbs/README.md)。

## 目录结构

```txt
summaries-and-demos/
├── AGENTS.md              # 生成规范
├── README.md              # 本索引
├── sums/                  # 23 篇速读笔记 (纯 Markdown, 与源文件同名)
│   └── <章节名>.md
└── demos/                 # 90 个 .py + 2 个 langgraph.json (按章节分目录)
    └── <章节名>/
        └── <按内容命名>.py
```

## 怎么用

1. **先读笔记**：`sums/<章节名>.md`。每篇结构统一为「一句话定位 / 核心概念 / 心智模型 / 关键步骤与代码 / 易错点·混淆区分·坑」。
2. **再跑 demo**：`demos/<章节名>/<demo>.py`。多数 demo 顶部注释标明了依赖、所需环境变量与运行命令。
3. **对照原文**：笔记首行标注了对应的 `src/oss/langgraph/<章节名>.mdx`。

## 环境准备

```bash
pip install -U langgraph
```

按需追加（各 demo 注释中有说明）：

```bash
pip install langchain langchain-deepseek langchain-openai langsmith pytest python-dotenv
```

### 环境变量速查

所有 demo 启动时都会 `load_dotenv()` 自动向上读取仓库的 `src/oss/langgraph/.env`，**不需要手动 export**。

| 变量 | 用途 | 涉及的章节 |
|------|------|-----------|
| `DEEPSEEK_API_KEY` | chat model（统一用 `init_chat_model("deepseek:deepseek-chat")`） | quickstart、thinking-in-langgraph、workflows-agents、add-memory、streaming、event-streaming |
| `SILICONFLOW_API_KEY` + `SILICONFLOW_BASE_URL` | embedding（`BAAI/bge-m3`，`dims=1024`） | stores、add-memory |
| `LANGSMITH_API_KEY` | 追踪 | observability、studio |
| `LANGSMITH_TRACING` | 开启追踪（observability / studio 的 demo 在未设置时会自动设为 `true`） | observability、studio |
| `LANGSMITH_DEPLOYMENT_URL` | 调用已部署 agent（**不在 `.env` 中，需自行提供**） | deploy |
| `LANGGRAPH_AES_KEY`（可选） | checkpoint 加密 | checkpointers |

> 无需任何 API key 即可运行的章节：overview、application-structure、backward-compatibility、persistence、checkpointers、fault-tolerance、interrupts、use-time-travel、use-subgraphs、local-server、test（纯图逻辑 / 本地服务 / 测试）。

## 章节索引

### 一、入门

| 章节 (源 mdx) | 笔记 | demo | 说明 | 依赖 |
|---------------|------|------|------|------|
| `overview.mdx` | [sums/overview.md](./sums/overview.md) | 1 | LangGraph 定位（底层编排 runtime）、确定性 + agentic 混合、五产品分工、hello world 骨架 | 无 |
| `install.mdx` | [sums/install.md](./sums/install.md) | 0 | 三层依赖（langgraph 必装 / langchain 可选 / provider 单独装）、Python 3.10+ | — |
| `quickstart.mdx` | [sums/quickstart.md](./sums/quickstart.md) | 2 | 计算器 agent：Graph API 六步 vs Functional API 四步 | `DEEPSEEK_API_KEY` |
| `application-structure.mdx` | [sums/application-structure.md](./sums/application-structure.md) | 1 (+json) | 四要素（graph / langgraph.json / 依赖 / env）、`路径:变量` 语法 | 无 |

### 二、思维与工作流

| 章节 (源 mdx) | 笔记 | demo | 说明 | 依赖 |
|---------------|------|------|------|------|
| `thinking-in-langgraph.mdx` | [sums/thinking-in-langgraph.md](./sums/thinking-in-langgraph.md) | 4 | 五步法（拆步骤 → 定跳转 → 共享 state）、state 设计、错误处理 | `DEEPSEEK_API_KEY`（`email_agent_full`） |
| `workflows-agents.mdx` | [sums/workflows-agents.md](./sums/workflows-agents.md) | 9 | 7 种编排模式：LLM 增强 / prompt chaining / 并行化 / 路由 / orchestrator-worker / evaluator-optimizer / agents | `DEEPSEEK_API_KEY` |
| `backward-compatibility.mdx` | [sums/backward-compatibility.md](./sums/backward-compatibility.md) | 2 | 三类兼容性（技术 / 业务 / 非确定性）、flow_version 分支 | 无 |

### 三、持久化与记忆

| 章节 (源 mdx) | 笔记 | demo | 说明 | 依赖 |
|---------------|------|------|------|------|
| `persistence.mdx` | [sums/persistence.md](./sums/persistence.md) | 1 | Persistence 概念总览（checkpointer + store） | 无 |
| `checkpointers.mdx` | [sums/checkpointers.md](./sums/checkpointers.md) | 5 | 线程级 checkpoint、durability、序列化、update_state / replay | 无 |
| `stores.mdx` | [sums/stores.md](./sums/stores.md) | 4 | 跨线程长期记忆、namespace、语义检索 | `SILICONFLOW_API_KEY`（`semantic_search`） |
| `add-memory.mdx` | [sums/add-memory.md](./sums/add-memory.md) | 8 | 短期记忆、消息 trim / summarize / delete、长期记忆与语义检索 | `DEEPSEEK_API_KEY`、`SILICONFLOW_API_KEY` |

### 四、流式

| 章节 (源 mdx) | 笔记 | demo | 说明 | 依赖 |
|---------------|------|------|------|------|
| `streaming.mdx` | [sums/streaming.md](./sums/streaming.md) | 10 | `stream_mode` 全模式、v2 StreamPart、messages / custom / subgraph / debug、任意 LLM | `DEEPSEEK_API_KEY` |
| `event-streaming.mdx` | [sums/event-streaming.md](./sums/event-streaming.md) | 6 | 两层事件架构、投影与并发消费、interrupt 恢复、自定义 transformer | `DEEPSEEK_API_KEY` |

### 五、容错

| 章节 (源 mdx) | 笔记 | demo | 说明 | 依赖 |
|---------------|------|------|------|------|
| `fault-tolerance.mdx` | [sums/fault-tolerance.md](./sums/fault-tolerance.md) | 9 | RetryPolicy、TimeoutPolicy（run / idle / heartbeat）、error handler、优雅关闭 | 无 |

### 六、控制流与人机交互

| 章节 (源 mdx) | 笔记 | demo | 说明 | 依赖 |
|---------------|------|------|------|------|
| `interrupts.mdx` | [sums/interrupts.md](./sums/interrupts.md) | 8 | `interrupt` + `Command(resume)` 五大模式、铁律与坑清单 | 无 |
| `use-time-travel.mdx` | [sums/use-time-travel.md](./sums/use-time-travel.md) | 5 | replay 与 fork、`as_node` 场景、遇 interrupt 重触发 | 无 |
| `use-subgraphs.mdx` | [sums/use-subgraphs.md](./sums/use-subgraphs.md) | 6 | 两种通信模式、三种 persistence 能力对照、state inspection | 无 |

### 七、工程与运维

| 章节 (源 mdx) | 笔记 | demo | 说明 | 依赖 |
|---------------|------|------|------|------|
| `deploy.mdx` | [sums/deploy.md](./sums/deploy.md) | 1 | 部署到 LangSmith Cloud、API URL、SDK 调用 | `LANGSMITH_DEPLOYMENT_URL`（需自行提供） |
| `local-server.mdx` | [sums/local-server.md](./sums/local-server.md) | 2 | `langgraph CLI`、`langgraph dev` 本地服务器、sync / async 调用 | 需本地服务 |
| `studio.mdx` | [sums/studio.md](./sums/studio.md) | 1 (+json) | LangSmith Studio 可视化调试、热重载与断点重跑 | `LANGSMITH_API_KEY`、需本地服务 |
| `test.mdx` | [sums/test.md](./sums/test.md) | 3 | 三种测试：端到端、单 node、部分执行（pytest） | `pytest` |
| `observability.mdx` | [sums/observability.md](./sums/observability.md) | 2 | trace / run、选择性追踪、tags / metadata、anonymizer 脱敏 | `LANGSMITH_API_KEY`、`DEEPSEEK_API_KEY` |
| `ui.mdx` | [sums/ui.md](./sums/ui.md) | 0 | Agent Chat UI（Next.js）托管版 / 本地版启动与配置 | — |

## 无 demo 的章节

`install.mdx` 与 `ui.mdx` 属安装说明与 UI / 运维说明，本身无可独立运行的代码，故仅产出笔记。

## 运行提示

- 需要 LLM 的 demo 会在文件头部注释中标注依赖与所需 key。
- 所有 demo 都会 `load_dotenv()` 自动读取仓库的 `src/oss/langgraph/.env`，无需手动 export；
  chat model 统一为 DeepSeek，embedding 统一为硅基流动 `BAAI/bge-m3`。
- `demos/test/` 下为 pytest 用例，运行：`pytest demos/test/`。
- `demos/application-structure/` 与 `demos/studio/` 含 `langgraph.json`，可用 `langgraph dev` 启动（在对应目录下执行）。
- `demos/local-server/`、`demos/deploy/` 需要先有运行中的服务（本地 `langgraph dev` 或已部署实例）。
- 超时相关 demo（`demos/fault-tolerance/timeouts.py` 等）使用 async node；同步 node + timeout 会编译失败。
