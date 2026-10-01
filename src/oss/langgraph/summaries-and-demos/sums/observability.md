# LangSmith 可观测性 (Observability) — 速读笔记

源文件: `src/oss/langgraph/observability.mdx`

## 核心概念

- **trace**: 应用从输入到输出经历的一系列步骤。
- **run**: trace 中每一个单独的步骤。
- 用 [LangSmith](https://smith.langchain.com) 可视化这些执行步骤, 三大用途:
  - 调试本地运行的应用
  - 评估应用性能
  - 监控应用
- 前置: LangSmith 账号 + LangSmith API key。
- 使用前需**为应用启用追踪** (`trace-with-langgraph`)。

## 关键步骤

### 启用追踪 (环境变量)
```bash
export LANGSMITH_TRACING=true
export LANGSMITH_API_KEY=<your-api-key>
```
- 默认记录到名为 `default` 的项目。

### 选择性追踪 (只追踪部分调用)
用 LangSmith 的 `tracing_context` 上下文管理器:
```python
import langsmith as ls

# 这段会被追踪
with ls.tracing_context(enabled=True):
    agent.invoke({"messages": [{"role": "user", "content": "Send a test email to alice@example.com"}]})

# 这段不会被追踪 (前提是 LANGSMITH_TRACING 未设置)
agent.invoke({"messages": [{"role": "user", "content": "Send another email"}]})
```

### 记录到项目
- 静态设置 (全局): 设环境变量
  ```bash
  export LANGSMITH_PROJECT=my-agent-project
  ```
- 动态设置 (编程控制):
  ```python
  import langsmith as ls

  with ls.tracing_context(project_name="email-agent-test", enabled=True):
      response = agent.invoke({
          "messages": [{"role": "user", "content": "Send a welcome email"}]
      })
  ```

### 为 trace 添加 metadata / tags
- 通过 `config`:
  ```python
  response = agent.invoke(
      {"messages": [{"role": "user", "content": "Send a welcome email"}]},
      config={
          "tags": ["production", "email-assistant", "v1.0"],
          "metadata": {
              "user_id": "user_123",
              "session_id": "session_456",
              "environment": "production"
          }
      }
  )
  ```
- `tracing_context` 也接受 `tags` 与 `metadata`, 实现更细粒度控制。
- 这些 tags/metadata 会附加到 LangSmith 中的 trace 上。

### 用 anonymizer 脱敏敏感数据
- 目的: 防止敏感数据被记录到 LangSmith。
- 创建 anonymizer, 通过配置应用到 graph 上。示例脱敏 SSN (社会安全号码, 格式 `XXX-XX-XXXX`):
  ```python
  from langchain_core.tracers.langchain import LangChainTracer
  from langgraph.graph import StateGraph, MessagesState
  from langsmith import Client
  from langsmith.anonymizer import create_anonymizer

  anonymizer = create_anonymizer([
      # 匹配 SSN
      {"pattern": r"\b\d{3}-?\d{2}-?\d{4}\b", "replace": "<ssn>"}
  ])

  tracer_client = Client(anonymizer=anonymizer)
  tracer = LangChainTracer(client=tracer_client)
  graph = (
      StateGraph(MessagesState)
      ...
      .compile()
      .with_config({'callbacks': [tracer]})
  )
  ```

## 心智模型

- **trace ⊃ run**: 一次调用 = 一条 trace, trace 内每步 = 一个 run; 可视化就是把这棵树展开。
- **默认开 / 可关 / 可选择**: 环境变量是全局开关; `tracing_context(enabled=True)` 是局部开关 (在没有全局开启时, 只在 with 块内追踪)。
- **项目名 = 数据的归属容器**: `LANGSMITH_PROJECT` 管全局, `tracing_context(project_name=...)` 管局部。
- **metadata/tags 是"给 trace 贴标签"**, 用于过滤、分组、排查。
- **anonymizer 位于数据出站前**: 它在 graph 与 LangSmith 之间拦截并替换敏感字段。

## 易错点 / 注意事项

- **选择性追踪的语义**是: `tracing_context(enabled=True)` 打开该块; 块外的调用在 `LANGSMITH_TRACING` 未设置时**不会**被追踪。别把两者搞混。
- **`LANGSMITH_PROJECT` (环境变量) 与 `project_name` (上下文参数) 都可能生效**, 动态设置会覆盖/局部生效, 别指望两者叠加来自动合并。
- **脱敏必须挂在 tracer client 上**: 是先 `create_anonymizer` → `Client(anonymizer=...)` → `LangChainTracer(client=...)` → 通过 `with_config({'callbacks': [tracer]})` 应用到 graph, 顺序不能错。
- **anonymizer 的 pattern 是正则**, 要按目标格式写 (示例匹配 SSN), 正则写错会漏脱敏或过度替换。
- 若关心隐私, 可结合 Studio 笔记里的 `LANGSMITH_TRACING=false` 完全关闭外发, 与 anonymizer 是两种不同强度的手段。
