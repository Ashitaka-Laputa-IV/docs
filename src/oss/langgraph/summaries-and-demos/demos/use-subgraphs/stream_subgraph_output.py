"""stream subgraph 输出: 用 event streaming 观察嵌套 run。

要点:
- 推荐用 stream.subgraphs 投影: 自动发现每个嵌套 run, 暴露 path / messages / values,
  无需解析 namespace 字符串。
- namespace 为空 ([]) = 父 graph 的事件; 非空 = 对应 subgraph 内部事件。

运行: python stream_subgraph_output.py
"""

from typing_extensions import TypedDict

from langgraph.graph import START, StateGraph


class SubgraphState(TypedDict):
    foo: str
    bar: str


def subgraph_node_1(state: SubgraphState):
    return {"bar": "bar"}


def subgraph_node_2(state: SubgraphState):
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
builder.add_node("node_2", subgraph)
builder.add_edge(START, "node_1")
builder.add_edge("node_1", "node_2")
graph = builder.compile()

# 观察嵌套的 graph 执行
stream = graph.stream_events({"foo": "foo"}, version="v3")
for sub in stream.subgraphs:
    print(sub.graph_name, sub.path)
    for snapshot in sub.values:
        print(sub.path, snapshot)
