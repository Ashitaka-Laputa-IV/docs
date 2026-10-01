"""在 node 内部调用 subgraph (父子拥有不同的 state schema)。

要点:
- 父与子没有共享 key, 因此需要包装函数显式转换 state。
- 典型用途: multi-agent 中为每个 agent 保留私有 message 历史。
- 可多级嵌套 (parent -> child -> grandchild), 逐层转换。

运行: python call_subgraph_in_node.py
"""

from typing_extensions import TypedDict

from langgraph.graph import START, StateGraph


# ---------- Subgraph: 使用独立的 SubgraphState ----------
class SubgraphState(TypedDict):
    # 注意: 这些 key 都不与父 graph 共享
    bar: str
    baz: str


def subgraph_node_1(state: SubgraphState):
    return {"baz": "baz"}


def subgraph_node_2(state: SubgraphState):
    return {"bar": state["bar"] + state["baz"]}


subgraph_builder = StateGraph(SubgraphState)
subgraph_builder.add_node("subgraph_node_1", subgraph_node_1)
subgraph_builder.add_node("subgraph_node_2", subgraph_node_2)
subgraph_builder.add_edge(START, "subgraph_node_1")
subgraph_builder.add_edge("subgraph_node_1", "subgraph_node_2")
subgraph = subgraph_builder.compile()


# ---------- Parent graph ----------
class ParentState(TypedDict):
    foo: str


def node_1(state: ParentState):
    return {"foo": "hi! " + state["foo"]}


def node_2(state: ParentState):
    # 把父 state 转换为 subgraph state
    response = subgraph.invoke({"bar": state["foo"]})
    # 把 subgraph 输出转换回父 state
    return {"foo": response["bar"]}


builder = StateGraph(ParentState)
builder.add_node("node_1", node_1)
builder.add_node("node_2", node_2)
builder.add_edge(START, "node_1")
builder.add_edge("node_1", "node_2")
graph = builder.compile()

result = graph.invoke({"foo": "foo"})
print(result)  # -> {'foo': 'hi! foobaz'}
