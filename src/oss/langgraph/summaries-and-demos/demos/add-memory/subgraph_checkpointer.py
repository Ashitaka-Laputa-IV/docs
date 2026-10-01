"""Subgraph + checkpointer: 只在父 graph 编译时传 checkpointer, 会自动传播给 subgraph。

对应 add-memory.mdx「在 subgraphs 中使用」。
不需要 API key。
"""

from typing import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, StateGraph


class State(TypedDict):
    foo: str


def subgraph_node_1(state: State):
    return {"foo": state["foo"] + "bar"}


def parent_node(state: State):
    return {"foo": state["foo"] + "-"}


def main() -> None:
    # --- subgraph: 自己编译时不带 checkpointer ---
    subgraph_builder = StateGraph(State)
    subgraph_builder.add_node(subgraph_node_1)
    subgraph_builder.add_edge(START, "subgraph_node_1")
    subgraph = subgraph_builder.compile()  # 父 graph 会自动传播 checkpointer

    # --- parent graph ---
    builder = StateGraph(State)
    builder.add_node("node_1", subgraph)
    builder.add_node("node_2", parent_node)
    builder.add_edge(START, "node_1")
    builder.add_edge("node_1", "node_2")

    checkpointer = InMemorySaver()
    graph = builder.compile(checkpointer=checkpointer)

    config = {"configurable": {"thread_id": "1"}}
    graph.invoke({"foo": "foo"}, config)
    print("最终 state:", graph.get_state(config).values)

    # 若想让 subgraph 拥有独立 checkpointing, 可改为:
    # subgraph = subgraph_builder.compile(checkpointer=True)


if __name__ == "__main__":
    main()
