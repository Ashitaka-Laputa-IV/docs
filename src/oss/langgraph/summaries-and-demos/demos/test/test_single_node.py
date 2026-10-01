"""测试单个 node (绕过 checkpointer)。

来源: src/oss/langgraph/test.mdx

前置: pip install -U pytest langgraph
运行: pytest test_single_node.py

要点: 编译后的 graph 通过 graph.nodes 暴露每个单独 node; 直接调用会绕过编译时传入的 checkpointer。
"""

from typing_extensions import TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph


def create_graph() -> StateGraph:
    class MyState(TypedDict):
        my_key: str

    graph = StateGraph(MyState)
    graph.add_node("node1", lambda state: {"my_key": "hello from node1"})
    graph.add_node("node2", lambda state: {"my_key": "hello from node2"})
    graph.add_edge(START, "node1")
    graph.add_edge("node1", "node2")
    graph.add_edge("node2", END)
    return graph


def test_individual_node_execution() -> None:
    # 本例中 checkpointer 会被忽略 (直接调用单个 node 会绕过它)
    checkpointer = MemorySaver()
    graph = create_graph()
    compiled_graph = graph.compile(checkpointer=checkpointer)
    # 只调用 node1
    result = compiled_graph.nodes["node1"].invoke(
        {"my_key": "initial_value"},
    )
    assert result["my_key"] == "hello from node1"
