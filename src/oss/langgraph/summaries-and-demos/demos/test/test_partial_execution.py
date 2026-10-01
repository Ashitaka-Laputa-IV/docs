"""测试 graph 的部分执行 (只跑 node2 → node3)。

来源: src/oss/langgraph/test.mdx

前置: pip install -U pytest langgraph
运行: pytest test_partial_execution.py

要点:
    - update_state(as_node="node1") 伪造"来自 node1 的中间 state", 执行从 node2 恢复。
    - invoke(None, ...) 传 None 表示恢复执行。
    - interrupt_after="node3" 让 node4 不运行。
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
    graph.add_node("node3", lambda state: {"my_key": "hello from node3"})
    graph.add_node("node4", lambda state: {"my_key": "hello from node4"})
    graph.add_edge(START, "node1")
    graph.add_edge("node1", "node2")
    graph.add_edge("node2", "node3")
    graph.add_edge("node3", "node4")
    graph.add_edge("node4", END)
    return graph


def test_partial_execution_from_node2_to_node3() -> None:
    checkpointer = MemorySaver()
    graph = create_graph()
    compiled_graph = graph.compile(checkpointer=checkpointer)

    compiled_graph.update_state(
        config={"configurable": {"thread_id": "1"}},
        # 传给 node2 的 state —— 模拟 node1 结束时的状态
        values={"my_key": "initial_value"},
        # 把保存的 state 当作来自 node1, 执行将从 node2 恢复
        as_node="node1",
    )

    result = compiled_graph.invoke(
        # 传 None 表示恢复执行
        None,
        config={"configurable": {"thread_id": "1"}},
        # 在 node3 之后停止, 让 node4 不运行
        interrupt_after="node3",
    )
    assert result["my_key"] == "hello from node3"
