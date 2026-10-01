"""把 subgraph 作为 node 添加 (父子共享 state key)。

要点:
- 直接传编译好的 subgraph 给 add_node, 无需包装函数。
- subgraph 自动读写父 graph 的 state 通道。
- subgraph 可以有父 graph 看不到的私有 key (bar), 同时更新共享 key (foo)。

运行: python subgraph_as_node.py
"""

from typing_extensions import TypedDict

from langgraph.graph import START, StateGraph


class SubgraphState(TypedDict):
    foo: str  # 与父 graph 共享
    bar: str  # SubgraphState 私有, 父 graph 不可见


def subgraph_node_1(state: SubgraphState):
    return {"bar": "bar"}


def subgraph_node_2(state: SubgraphState):
    # 使用仅供 subgraph 使用的 key ('bar'), 并更新共享 key ('foo')
    return {"foo": state["foo"] + state["bar"]}


subgraph_builder = StateGraph(SubgraphState)
subgraph_builder.add_node("subgraph_node_1", subgraph_node_1)
subgraph_builder.add_node("subgraph_node_2", subgraph_node_2)
subgraph_builder.add_edge(START, "subgraph_node_1")
subgraph_builder.add_edge("subgraph_node_1", "subgraph_node_2")
subgraph = subgraph_builder.compile()


class ParentState(TypedDict):
    foo: str


def node_1(state: ParentState):
    return {"foo": "hi! " + state["foo"]}


builder = StateGraph(ParentState)
builder.add_node("node_1", node_1)
builder.add_node("node_2", subgraph)  # 直接传编译好的 subgraph
builder.add_edge(START, "node_1")
builder.add_edge("node_1", "node_2")
graph = builder.compile()

result = graph.invoke({"foo": "foo"})
print(result)  # -> {'foo': 'hi! foobar'}
