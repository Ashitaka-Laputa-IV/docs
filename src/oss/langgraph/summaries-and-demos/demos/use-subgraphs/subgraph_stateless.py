"""无状态 subgraph (checkpointer=False): 像普通函数调用, 无 checkpoint 开销。

警告:
    没有 checkpoint 就没有持久化执行。若进程运行中途崩溃,
    subgraph 无法恢复, 必须从头重新运行。
    也无法使用 interrupt() 暂停 / 恢复。

运行: python subgraph_stateless.py
"""

from typing_extensions import TypedDict

from langgraph.graph import START, StateGraph


class State(TypedDict):
    foo: str


def subgraph_node_1(state: State):
    return {"foo": "hi! " + state["foo"]}


subgraph_builder = StateGraph(State)
subgraph_builder.add_node("subgraph_node_1", subgraph_node_1)
subgraph_builder.add_edge(START, "subgraph_node_1")

# 完全不 checkpoint
subgraph = subgraph_builder.compile(checkpointer=False)

builder = StateGraph(State)
builder.add_node("node_1", subgraph)
builder.add_edge(START, "node_1")
graph = builder.compile()

print(graph.invoke({"foo": "foo"}))  # -> {'foo': 'hi! foo'}
