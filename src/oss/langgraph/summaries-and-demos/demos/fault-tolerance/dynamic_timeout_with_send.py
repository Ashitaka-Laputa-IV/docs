"""fault-tolerance.mdx: 用 Send 实现动态 (单次) 超时。

用 Send 动态派发 node 时, 可在 Send 上传超时, 覆盖目标 node 的静态超时。
省略时用目标 node 在 add_node 时设置的超时。

依赖: pip install langgraph
运行: python dynamic_timeout_with_send.py
"""

from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send, TimeoutPolicy


class OverallState(TypedDict):
    items: list
    results: list


class ItemState(TypedDict):
    item: str
    results: list


def process_item(state: ItemState):
    return {"results": [f"processed:{state['item']}"]}


def fan_out(state: OverallState):
    # 针对每次推送收紧空闲超时为 15 秒
    return [
        Send("process_item", {"item": item, "results": []}, timeout=TimeoutPolicy(idle_timeout=15))
        for item in state["items"]
    ]


builder = StateGraph(OverallState)
builder.add_node("process_item", process_item)
builder.add_conditional_edges(START, fan_out, ["process_item"])
builder.add_edge("process_item", END)
graph = builder.compile()


if __name__ == "__main__":
    print(graph.invoke({"items": ["a", "b", "c"], "results": []}))
