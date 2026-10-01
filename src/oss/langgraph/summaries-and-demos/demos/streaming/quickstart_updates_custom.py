"""streaming.mdx 快速开始: 同时使用 updates + custom 两个 stream mode (v2 格式)。

依赖: pip install langgraph
运行: python quickstart_updates_custom.py
"""

from typing import TypedDict

from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph


class State(TypedDict):
    topic: str
    joke: str


def generate_joke(state: State):
    # 在 node 内获取 stream writer, 发出自定义数据
    writer = get_stream_writer()
    writer({"status": "thinking of a joke..."})
    return {"joke": f"Why did the {state['topic']} go to school? To get a sundae education!"}


graph = (
    StateGraph(State)
    .add_node(generate_joke)
    .add_edge(START, "generate_joke")
    .add_edge("generate_joke", END)
    .compile()
)


if __name__ == "__main__":
    for chunk in graph.stream(
        {"topic": "ice cream"},
        stream_mode=["updates", "custom"],  # 可传多个 mode
        version="v2",                        # v2: 统一 StreamPart 格式
    ):
        # 每个 chunk 都是 {"type", "ns", "data"} 形状
        if chunk["type"] == "updates":
            for node_name, state in chunk["data"].items():
                print(f"Node {node_name} updated: {state}")
        elif chunk["type"] == "custom":
            print(f"Status: {chunk['data']['status']}")

    # 预期输出:
    # Status: thinking of a joke...
    # Node generate_joke updated: {'joke': 'Why did the ice cream go to school? To get a sundae education!'}
