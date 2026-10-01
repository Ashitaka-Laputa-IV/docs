# LangGraph 概览 — 速读笔记

源文件: `src/oss/langgraph/overview.mdx`

## 一句话定位

LangGraph 是一个**底层编排 framework 与 runtime**, 用于构建、管理和部署**长时运行、有状态**的 agent。它非常底层, 完全专注于 agent **编排**。

## 核心概念

- **编排 (orchestration) 是唯一关注点**: LangGraph 不对 prompt 或架构做抽象, 只负责把 agent 的执行流程管起来。
- **确定性步骤 + agentic 步骤混合**: 在同一个 graph 中, 既可以有手工编写、完全可预测可审计的确定性逻辑, 也可以有 LLM 驱动的 agentic 决策。这是它最核心的差异化优势。
- **有状态**: state 在整个执行期间持续存在, 支持中断恢复。
- **不绑定 LangChain**: 可用 LangChain 组件来集成 models / tools (文档默认这么做), 但 L**不需要** LangChain 也能用 LangGraph。
- **灵感来源**: Pregel、Apache Beam (运行模型), NetworkX (公开接口)。

## 心智模型: 五个产品各自的位置

| 产品 | 定位 |
|------|------|
| Deep Agents | agent harness: 在 LangGraph 之上提供 planning、subagents、filesystem tools、上下文管理 |
| LangChain | agent framework: 为 models、tools、agent loop 提供抽象与集成 |
| LangGraph | **编排 runtime**: durable execution、streaming、human-in-the-loop、persistence |
| LangSmith | 跨 framework 的追踪、evaluation、prompt 与部署平台 |
| LangSmith Engine | 检测 trace 中的问题并提出修复方案 (可直接开 PR) |
| LangSmith Fleet | no-code agent 构建器 |

记忆顺序: **harness (Deep Agents) → framework (LangChain) → runtime (LangGraph)**, LangSmith 是外围平台层。

## 关键步骤: 安装与最小示例

安装 (Python):

```bash
pip install -U langgraph
```

安装 (JS):

```bash
npm install @langchain/langgraph @langchain/core
```

最小 hello world (Python):

```python
from langgraph.graph import StateGraph, MessagesState, START, END

def mock_llm(state: MessagesState):
    return {"messages": [{"role": "ai", "content": "hello world"}]}

graph = StateGraph(MessagesState)
graph.add_node(mock_llm)
graph.add_edge(START, "mock_llm")
graph.add_edge("mock_llm", END)
graph = graph.compile()

graph.invoke({"messages": [{"role": "user", "content": "hi!"}]})
```

这个示例展示了 LangGraph 的最小骨架: **选 state schema → add_node → 连 START/END → compile → invoke**。

## 核心优势 (官方列举)

- **混合确定性步骤与 agentic 步骤**: 在需要可靠性与可预测性处用确定性步骤, 在需要灵活性处用 agentic 步骤。
- **Persistence**: agent 遭遇故障也能继续, 可从上次中断处恢复。
- **Human-in-the-loop**: 任意时刻检查并修改 agent state。
- **全面的 memory**: short-term working memory (持续推理) + long-term memory (跨会话)。
- **LangSmith 调试**: 追踪执行路径、捕获 state 转换、提供 runtime 指标。
- **生产就绪的部署**: 可扩展基础设施, 应对有状态、长时运行 workflow。

## 生态集成

LangGraph 可单独使用, 也可与 LangChain 产品集成:

| 搭配产品 | 用途 |
|----------|------|
| LangSmith Observability | 追踪请求、评估输出、监控部署; 本地原型 → 生产 |
| LangSmith Deployment | 部署与扩展长时运行、有状态 agent; Studio 可视化原型 |
| LangChain | 提供集成与可组合组件; 含构建在 LangGraph 之上的 agent 抽象 |

## 易错点 / 注意事项

- **不要以为必须装 LangChain 才能用 LangGraph**: LangGraph 独立可用。文档用 LangChain 只是为了方便集成 models/tools。
- **LangGraph 不做抽象**: 如果你想要更高层抽象、prebuilt 的 LLM + tool-calling loop, 应该用 LangChain 的 `agents`, 而不是 LangGraph 本身。
- **前提建议**: 使用 LangGraph 前, 建议先熟悉 models 与 tools 组件 (`/oss/langchain/models`、`/oss/langchain/tools`)。
- **需要持久化时才加 checkpointer**: 概览里的 hello world 没配置持久化, 重启即丢状态; persistence 是 LangGraph 的另一项能力, 需显式配置才启用。
- **LangSmith 追踪需显式开启**: 设置 `LANGSMITH_TRACING=true` 与 API key 才开始追踪。
