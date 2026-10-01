"""使用 anonymizer 在写入 LangSmith 前脱敏敏感数据 (示例: 社会安全号码 SSN)。

来源: src/oss/langgraph/observability.mdx

依赖: pip install langgraph langsmith python-dotenv
API key: 自动读取仓库的 src/oss/langgraph/.env (DEEPSEEK_API_KEY / SILICONFLOW_API_KEY / LANGSMITH_API_KEY)
运行: python anonymize_traces.py

要点: 脱敏链路是
    create_anonymizer -> Client(anonymizer=...) -> LangChainTracer(client=...) -> with_config callbacks
"""

import os

from dotenv import load_dotenv

load_dotenv()  # 自动向上查找 src/oss/langgraph/.env
os.environ.setdefault("LANGSMITH_TRACING", "true")  # .env 未设置时开启追踪

from langchain_core.tracers.langchain import LangChainTracer
from langgraph.graph import MessagesState, StateGraph
from langsmith import Client
from langsmith.anonymizer import create_anonymizer


def echo(state: MessagesState) -> dict:
    """把用户输入原样回显(模拟会处理敏感数据的节点)。"""
    return {"messages": [{"role": "ai", "content": "received"}]}


# 匹配 SSN, 发送到 LangSmith 前替换为 <ssn>
anonymizer = create_anonymizer([
    {"pattern": r"\b\d{3}-?\d{2}-?\d{4}\b", "replace": "<ssn>"}
])

tracer_client = Client(anonymizer=anonymizer)
tracer = LangChainTracer(client=tracer_client)

graph = (
    StateGraph(MessagesState)
    .add_node("echo", echo)
    .add_edge("__start__", "echo")
    .compile()
    .with_config({"callbacks": [tracer]})
)


if __name__ == "__main__":
    result = graph.invoke(
        {"messages": [{"role": "human", "content": "My SSN is 123-45-6789"}]},
    )
    print(result["messages"][-1].content)
