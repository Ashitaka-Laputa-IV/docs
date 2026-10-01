# 安装 LangGraph — 速读笔记

源文件: `src/oss/langgraph/install.mdx`

## 核心概念

安装分两层:

1. **LangGraph 基础包** — 编排 runtime 本身, 必须装。
2. **可选的 LLM / tools 库** — LangGraph 不绑定具体实现, 你按自己的方式接入 LLM 和定义 tools。

## 关键步骤

### 第 1 步: 安装 LangGraph 基础包

Python:

```bash
pip install -U langgraph
# 或
uv add langgraph
```

JS / TS:

```bash
npm install @langchain/langgraph @langchain/core
# 或 pnpm add / yarn add / bun add 同两个包
```

### 第 2 步 (可选但文档默认): 安装 LangChain

文档通常用 LangChain 来集成 models 与 tools。

Python (需 Python 3.10+):

```bash
pip install -U langchain
# 或
uv add langchain
```

JS:

```bash
npm install langchain
```

### 第 3 步: 安装具体 LLM provider 包

要使用特定 LLM provider, 需**单独安装**对应集成包。具体安装说明见 integrations 的 providers 页面。

## 心智模型

- **LangGraph 只装编排层, 不装模型层**。LLM provider 包是分开的。
- **三层依赖**: `langgraph` (必装) → `langchain` (可选, 集成抽象) → provider 包 (按需)。
- 文档示例采用 LangChain 路线, 但你完全可以不用 LangChain, 手动接入 LLM 与 tools。

## 易错点 / 注意事项

- **版本要求**: Python 安装 langchain 需要 **Python 3.10+** (注释里明确写了)。
- **provider 包不会随 langgraph 自动安装**: 用 Anthropic / OpenAI 等都需要额外装对应包, 否则运行时报找不到模型。
- **JS 端基础包是两个**: `@langchain/langgraph` + `@langchain/core`, 只装前者可能报错。
- `pip install -U` 中的 `-U` 表示升级到最新版本, 更新环境时保留。
