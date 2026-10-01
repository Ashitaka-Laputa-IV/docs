# 应用结构 — 速读笔记

源文件: `src/oss/langgraph/application-structure.mdx`

## 一句话定位

一个 LangGraph 应用由四部分组成: **一个或多个 graph + 一个配置文件 (`langgraph.json`) + 一个依赖文件 + 可选的 `.env` 环境变量文件**。本文展示典型目录结构并说明如何提供配置, 以便用 LangSmith Deployment 部署。

## 核心概念: 部署需要提供什么

1. **LangGraph 配置文件** (`langgraph.json`): 指定依赖、graphs、环境变量。
2. **graphs**: 实现应用逻辑。
3. **依赖文件**: 声明运行所需依赖 (如 `requirements.txt` / `pyproject.toml` / `package.json`)。
4. **环境变量**: 运行所需的环境变量。

## 文件结构

Python (requirements.txt 风格):

```plaintext
my-app/
├── my_agent              # 所有项目代码
│   ├── utils             # graph 的工具函数
│   │   ├── __init__.py
│   │   ├── tools.py      # tools
│   │   ├── nodes.py      # node 函数
│   │   └── state.py      # state 定义
│   ├── __init__.py
│   └── agent.py          # 构建 graph 的代码
├── .env                  # 环境变量
├── requirements.txt      # 依赖
└── langgraph.json        # 配置文件
```

Python (pyproject.toml 风格): 同上, 只是把 `requirements.txt` 换成 `pyproject.toml`。

JS / TS:

```plaintext
my-app/
├── src                   # 所有项目代码
│   ├── utils             # 可选的工具函数
│   │   ├── tools.ts
│   │   ├── nodes.ts
│   │   └── state.ts
│   └── agent.ts          # 构建 graph 的代码
├── package.json          # 依赖
├── .env                  # 环境变量
└── langgraph.json        # 配置文件
```

注意: 目录结构**因语言与包管理器而异**。Python 代码放在包目录 `my_agent/`; JS 放在 `src/`。

## 配置文件 `langgraph.json`

用 JSON 指定**依赖、graphs、环境变量及其他设置**。所有受支持的键见 LangGraph 配置文件参考。

**默认路径**: LangGraph CLI 默认读取当前目录下的 `langgraph.json`, 无需手动指定路径。

Python 示例:

```json
{
  "dependencies": ["langchain_openai", "./your_package"],
  "graphs": {
    "my_agent": "./your_package/your_file.py:agent"
  },
  "env": "./.env"
}
```

- 依赖包含一个自定义本地包 `./your_package` 与 `langchain_openai`。
- `graphs` 的 value 是 `路径:变量名`, 从 `./your_package/your_file.py` 加载变量 `agent`。
- `env` 指向 `.env` 文件。

JS 示例:

```json
{
  "dependencies": ["."],
  "graphs": {
    "my_agent": "./your_package/your_file.js:agent"
  },
  "env": {
    "OPENAI_API_KEY": "secret-key"
  }
}
```

- JS 依赖从本地目录的依赖文件 (如 `package.json`) 加载, 所以写 `"."`。
- `env` 可以内联写成对象。

## 依赖

- 指定一个依赖文件 (`requirements.txt`、`pyproject.toml` 或 `package.json`)。
- 用配置文件的 `dependencies` 键列出运行所需的依赖。
- 额外的二进制文件或系统库用配置文件的 `dockerfile_lines` 键指定。

## Graphs

- 用配置文件的 `graphs` 键声明部署后哪些 graph 可用。
- 可指定**一个或多个** graph。
- 每个 graph 由**唯一名称** + 一个路径标识; 路径指向: (1) 一个**已编译的 graph**, 或 (2) 一个**用于构建 graph 的函数**。

## 环境变量

- 本地使用已部署应用时, 在配置文件的 `env` 键中配置环境变量。
- **生产部署**通常应把环境变量配置在部署环境中, 而不是写进仓库文件。

## 心智模型

- **`langgraph.json` 是应用的"入口清单"**: 告诉平台 "装什么依赖、有哪些 graph、变量在哪"。
- **`路径:变量` 语法**是 graph 定位的核心约定 (Python 是文件路径 + 变量名)。
- **本地 vs 生产的配置分层**: 本地用 `.env` / 内联, 生产用部署环境变量。

## 易错点 / 注意事项

- **graph 名称必须唯一**: 多个 graph 的 key 不能重复。
- **`graphs` 的值格式是 `文件路径:变量名`**, 冒号后的变量名必须真实存在 (是编译后的 graph 或构建函数)。
- **JS 的 `dependencies` 用 `"."`** (从本地 package.json 读取), 不要照抄 Python 的包名列表。
- **不要提交密钥**: 生产环境变量应配置在部署环境; 示例里内联的 `"secret-key"` 只是演示, 切勿照抄真实 key。
- **别混淆 `.env` 与 `langgraph.json`**: 前者只放环境变量, 后者是应用配置清单。
