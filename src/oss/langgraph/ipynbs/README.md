# LangGraph 教程 Jupyter Notebook 索引

本目录是对 `src/oss/langgraph/` 下**已翻译为中文的章节**(共 23 篇)所做的 Jupyter Notebook 版本。

- 生成规范见 [`AGENTS.md`](./AGENTS.md)：源文件为中文 `.mdx`，产物为**同名 `.ipynb`**。
- notebook 内容严格来自源 mdx 的**中文正文 + Python 示例代码**：只保留 Python 分支(删掉 TypeScript 版)，
  不自行编造。文档里引用未定义符号的**讲解型片段**原样保留为 Markdown 代码块，不作为可执行 cell。
- 每个 notebook 都**已真实执行过**，输出写回在文件里，打开即可阅读结果。

## 目录结构

```txt
ipynbs/
├── AGENTS.md          # 生成规范
├── README.md          # 本索引
└── <章节名>.ipynb     # 23 个 notebook, 与源 mdx 同名
```

## 怎么用

1. **直接读**：在 GitHub / VS Code / Jupyter 里打开 `<章节名>.ipynb`，cell 里已经带上执行输出。
2. **自己重跑**：装好依赖(见下)，从第一个 cell 开始顺序执行——每个 notebook 都是从上到下可以一次跑完的。
3. **对照原文**：notebook 的 H1 标题就是 `src/oss/langgraph/<章节名>.mdx` 的 `title`。

## 环境准备

```bash
pip install -U langgraph langchain langchain-deepseek langchain-openai python-dotenv jupyter
```

## 环境变量速查

带代码 cell 的 notebook 第一个 cell 会自动 `load_dotenv()`，向上找到**仓库根目录**（`pyproject.toml` 同目录）的 `.env`，
所以只要该文件里有对应的键，就直接可跑，不需要手动 `export`。仓库里提供了模板：

```bash
cp .env.example .env   # 再填入真实值
```

| 变量 | 用途 | 涉及的章节 |
|------|------|-----------|
| `DEEPSEEK_API_KEY` | chat model(`init_chat_model("deepseek:deepseek-chat")`) | quickstart、workflows-agents、add-memory、interrupts；streaming、thinking-in-langgraph、use-subgraphs 会构造模型对象 |
| `SILICONFLOW_API_KEY` + `SILICONFLOW_BASE_URL` | embedding(`BAAI/bge-m3`, `dims=1024`) | stores、add-memory |
| `LANGSMITH_API_KEY` | 追踪（仅 `studio` / `observability` 章节正文涉及，notebook 内未实际发起追踪调用） | studio、observability |

> 无需任何 API key 即可整篇跑通的章节：overview、application-structure、backward-compatibility、
> persistence、checkpointers、fault-tolerance、use-time-travel、test、install、ui、
> observability、event-streaming。

> **与源文档的差异**：notebook 把 provider 统一换成了 DeepSeek(chat)与硅基流动 bge-m3(embedding)，
> 源文档里原本是 Claude / OpenAI；正文中「需要注册 X 账号 / 设置 XXX_API_KEY」的说明已按约定删除。

## 章节索引

### 一、入门

| 章节 (源 mdx) | notebook | code cells | 说明 | 依赖 |
|---------------|----------|-----------|------|------|
| `overview.mdx` | [overview.ipynb](./overview.ipynb) | 2 | LangGraph 定位(底层编排 runtime)、确定性 + agentic 混合、五产品分工、hello world 骨架 | 无 |
| `install.mdx` | [install.ipynb](./install.ipynb) | 0 | 三层依赖(langgraph 必装 / langchain 可选 / provider 单独装)、Python 3.10+；内容为安装命令 | — |
| `quickstart.mdx` | [quickstart.ipynb](./quickstart.ipynb) | 11 | 计算器 agent：Graph API 六步 vs Functional API 四步 | `DEEPSEEK_API_KEY` |
| `application-structure.mdx` | [application-structure.ipynb](./application-structure.ipynb) | 0 | 应用四要素(graph / langgraph.json / 依赖 / env)、目录结构 | — |

### 二、思维与工作流

| 章节 (源 mdx) | notebook | code cells | 说明 | 依赖 |
|---------------|----------|-----------|------|------|
| `thinking-in-langgraph.mdx` | [thinking-in-langgraph.ipynb](./thinking-in-langgraph.ipynb) | 7 | 五步法(拆步骤 → 定跳转 → 共享 state)、state 设计、错误处理策略 | `DEEPSEEK_API_KEY` |
| `workflows-agents.mdx` | [workflows-agents.ipynb](./workflows-agents.ipynb) | 18 | 7 种编排模式：LLM 增强 / prompt chaining / 并行化 / 路由 / orchestrator-worker / evaluator-optimizer / agents | `DEEPSEEK_API_KEY` |
| `backward-compatibility.mdx` | [backward-compatibility.ipynb](./backward-compatibility.ipynb) | 2 | 三类兼容性(技术 / 业务 / 非确定性)、flow_version 分支 | 无 |

### 三、持久化与记忆

| 章节 (源 mdx) | notebook | code cells | 说明 | 依赖 |
|---------------|----------|-----------|------|------|
| `persistence.mdx` | [persistence.ipynb](./persistence.ipynb) | 2 | Persistence 概念总览(checkpointer + store) | 无 |
| `checkpointers.mdx` | [checkpointers.ipynb](./checkpointers.ipynb) | 5 | 线程级 checkpoint、durability、序列化、update_state / replay | 无 |
| `stores.mdx` | [stores.ipynb](./stores.ipynb) | 13 | 跨线程长期记忆、namespace、语义检索 | `SILICONFLOW_API_KEY` |
| `add-memory.mdx` | [add-memory.ipynb](./add-memory.ipynb) | 13 | 短期记忆、消息 trim / summarize / delete、长期记忆与语义检索 | `DEEPSEEK_API_KEY`、`SILICONFLOW_API_KEY` |

### 四、流式

| 章节 (源 mdx) | notebook | code cells | 说明 | 依赖 |
|---------------|----------|-----------|------|------|
| `streaming.mdx` | [streaming.ipynb](./streaming.ipynb) | 19 | `stream_mode` 全模式、v2 StreamPart、messages / custom / subgraph / debug、任意 LLM | `DEEPSEEK_API_KEY` |
| `event-streaming.mdx` | [event-streaming.ipynb](./event-streaming.ipynb) | 1 | 两层事件架构、投影与并发消费、interrupt 恢复、自定义 transformer；概念页 | —（仅环境准备 cell） |

### 五、容错

| 章节 (源 mdx) | notebook | code cells | 说明 | 依赖 |
|---------------|----------|-----------|------|------|
| `fault-tolerance.mdx` | [fault-tolerance.ipynb](./fault-tolerance.ipynb) | 6 | RetryPolicy、TimeoutPolicy(run / idle / heartbeat)、error handler、优雅关闭 | 无 |

### 六、控制流与人机交互

| 章节 (源 mdx) | notebook | code cells | 说明 | 依赖 |
|---------------|----------|-----------|------|------|
| `interrupts.mdx` | [interrupts.ipynb](./interrupts.ipynb) | 9 | `interrupt` + `Command(resume)` 五大模式、铁律与坑清单 | `DEEPSEEK_API_KEY` |
| `use-time-travel.mdx` | [use-time-travel.ipynb](./use-time-travel.ipynb) | 4 | replay 与 fork、`as_node` 场景、遇 interrupt 重触发 | 无 |
| `use-subgraphs.mdx` | [use-subgraphs.ipynb](./use-subgraphs.ipynb) | 9 | 两种通信模式、三种 persistence 能力对照、state inspection | `DEEPSEEK_API_KEY`（构造模型） |

### 七、工程与运维

| 章节 (源 mdx) | notebook | code cells | 说明 | 依赖 |
|---------------|----------|-----------|------|------|
| `deploy.mdx` | [deploy.ipynb](./deploy.ipynb) | 1 | 部署到 LangSmith Cloud、API URL、SDK 调用 | 需**已部署实例地址** |
| `local-server.mdx` | [local-server.ipynb](./local-server.ipynb) | 1 | `langgraph CLI`、`langgraph dev` 本地服务器、sync / async 调用 | 需本地**运行中的服务** |
| `studio.mdx` | [studio.ipynb](./studio.ipynb) | 2 | LangSmith Studio 可视化调试、热重载与断点重跑 | `DEEPSEEK_API_KEY`、需本地服务 |
| `test.mdx` | [test.ipynb](./test.ipynb) | 6 | 三种测试：端到端、单 node、部分执行 | `pytest` |
| `observability.mdx` | [observability.ipynb](./observability.ipynb) | 0 | trace / run、选择性追踪、tags / metadata、anonymizer 脱敏 | —（示例为片段，未执行） |
| `ui.mdx` | [ui.ipynb](./ui.ipynb) | 0 | Agent Chat UI(Next.js)托管版 / 本地版启动与配置 | — |

## 没有可执行 cell 的章节

以下 4 篇的源文档里**没有自包含、可直接运行的 Python 示例**，因此 notebook 只由正文与
Markdown 代码块组成(按「不自行编造代码」的约定，不去补写文档里没有的占位定义)：

| 章节 | 原因 |
|------|------|
| `install.mdx` | 只有 `pip` / `uv` / `npm` 安装命令 |
| `ui.mdx` | 只有 `npx` / `git clone` 等启动 Agent Chat UI 的命令 |
| `application-structure.mdx` | 只有目录结构与 `langgraph.json` 配置 |
| `observability.mdx` | 代码示例都是引用文档未定义的 `agent` 的片段 |

## 运行提示

- 参考型章节(`fault-tolerance`、`interrupts`、`checkpointers`、`streaming`、`event-streaming` 等)
  有较多 Markdown 代码块：它们引用文档里没有定义的名字，属于讲解片段，**不参与执行**；可执行的只有文档中自包含的完整示例。
- `local-server.ipynb` 需要先在本地起 `langgraph dev`；它的输出 cell 体积较大，因为文档示例会逐个打印流式 chunk。
- `deploy.ipynb` 的部署地址与 key 在文档里是占位符，无法真实调用，相关代码保留为 Markdown 代码块。
- 需要外部数据库(Postgres / Redis / Mongo 等)的示例因 `.env` 里没有连接串，也保留为 Markdown 代码块。
- `.ipynb_checkpoints` 已被 `.gitignore` 忽略。

## 相关

- 同一批章节的**速读笔记**与**最小可运行 demo**：见 [`../summaries-and-demos/`](../summaries-and-demos/README.md)。
