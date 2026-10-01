"""streaming.mdx: 用 custom mode stream node / tool 内部的自定义数据。

步骤:
1. 用 get_stream_writer() 获取 writer 并发出自定义数据。
2. stream 时设置 stream_mode="custom" (组合 mode 时至少要有一个 custom)。

依赖: pip install langgraph langchain-core
运行: python custom_data_writer.py
"""

from typing import TypedDict

from langchain_core.tools import tool
from langgraph.config import get_stream_writer
from langgraph.graph import START, StateGraph


class State(TypedDict):
    query: str
    answer: str


def node(state: State):
    # 获取 stream writer 发送自定义数据
    writer = get_stream_writer()
    # 发出自定义键值对 (例如进度更新)
    writer({"custom_key": "Generating custom data inside node"})
    return {"answer": "some data"}


graph = (
    StateGraph(State)
    .add_node(node)
    .add_edge(START, "node")
    .compile()
)


@tool
def query_database(query: str) -> str:
    """Query the database."""
    # 在 tool 内同样可以访问 stream writer
    writer = get_stream_writer()
    writer({"data": "Retrieved 0/100 records", "type": "progress"})
    # perform query ...
    writer({"data": "Retrieved 100/100 records", "type": "progress"})
    return "some-answer"


if __name__ == "__main__":
    print("=== node 发出的 custom 数据 ===")
    for chunk in graph.stream({"query": "example"}, stream_mode="custom", version="v2"):
        if chunk["type"] == "custom":
            print(f"Custom event: {chunk['data']['custom_key']}")

    # tool 内部 writer 的用法 (需在包含该 tool 的 graph 中运行):
    # for chunk in some_graph.stream(inputs, stream_mode="custom", version="v2"):
    #     if chunk["type"] == "custom":
    #         print(f"{chunk['data']['type']}: {chunk['data']['data']}")
    print("tool query_database defined:", query_database.name)
