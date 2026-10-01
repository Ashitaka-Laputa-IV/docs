"""streaming.mdx: 用 subgraphs=True 把 subgraph 的输出纳入 stream。

v2 下 subgraph 事件仍是 StreamPart, 用 chunk["ns"] 判断来源:
- () => 根 graph
- ("node_name:<task_id>",) => subgraph

依赖: pip install langgraph
运行: python subgraph_streaming.py
"""

from typing import TypedDict

from langgraph.graph import START, StateGraph


# 定义 subgraph
class SubgraphState(TypedDict):
    foo: str  # 注意该 key 与父 graph state 共享
    bar: str


def subgraph_node_1(state: SubgraphState):
    return {"bar": "bar"}


def subgraph_node_2(state: SubgraphState):
    return {"foo": state["foo"] + state["bar"]}


subgraph_builder = StateGraph(SubgraphState)
subgraph_builder.add_node(subgraph_node_1)
subgraph_builder.add_node(subgraph_node_2)
subgraph_builder.add_edge(START, "subgraph_node_1")
subgraph_builder.add_edge("subgraph_node_1", "subgraph_node_2")
subgraph = subgraph_builder.compile()


# 定义父 graph
class ParentState(TypedDict):
    foo: str


def node_1(state: ParentState):
    return {"foo": "hi! " + state["foo"]}


builder = StateGraph(ParentState)
builder.add_node("node_1", node_1)
builder.add_node("node_2", subgraph)
builder.add_edge(START, "node_1")
builder.add_edge("node_1", "node_2")
graph = builder.compile()


if __name__ == "__main__":
    for chunk in graph.stream(
        {"foo": "foo"},
        stream_mode="updates",
        subgraphs=True,   # 关键: 才能收到 subgraph 内部输出
        version="v2",
    ):
        if chunk["type"] == "updates":
            if chunk["ns"]:
                print(f"Subgraph {chunk['ns']}: {chunk['data']}")
            else:
                print(f"Root: {chunk['data']}")

    # 预期:
    # Root: {'node_1': {'foo': 'hi! foo'}}
    # Subgraph ('node_2:...',): {'subgraph_node_1': {'bar': 'bar'}}
    # Subgraph ('node_2:...',): {'subgraph_node_2': {'foo': 'hi! foobar'}}
    # Root: {'node_2': {'foo': 'hi! foobar'}}
