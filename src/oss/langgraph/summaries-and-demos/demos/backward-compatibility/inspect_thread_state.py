"""技术兼容性: 用 get_state / get_state_history 检查进行中的 thread。

LangGraph 本身不做 thread 索引, 要判断某个 thread 停在哪里, 需直接查询。
本 demo 用 InMemorySaver 演示, 不依赖 LLM / API key。
运行: python inspect_thread_state.py
"""

from typing import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph


class State(TypedDict):
    counter: int
    message: str


def inc_a(state: State) -> dict:
    return {"counter": state["counter"] + 1, "message": "after A"}


def inc_b(state: State) -> dict:
    return {"counter": state["counter"] + 1, "message": "after B"}


builder = StateGraph(State)
builder.add_node("a", inc_a)
builder.add_node("b", inc_b)
builder.add_edge(START, "a")
builder.add_edge("a", "b")
builder.add_edge("b", END)

memory = InMemorySaver()
graph = builder.compile(checkpointer=memory)


if __name__ == "__main__":
    config = {"configurable": {"thread_id": "thread_1"}}
    graph.invoke({"counter": 0, "message": "start"}, config)

    # 最新 checkpoint: 含 thread 当前停在哪个 node
    snapshot = graph.get_state(config)
    print("最新 state:", snapshot.values)
    print("下一步:", snapshot.next)

    # 完整按时间顺序的 checkpoint 列表
    history = list(graph.get_state_history(config))
    print(f"历史 checkpoint 数量: {len(history)}")
    for i, snap in enumerate(history):
        print(f"  #{i} next={snap.next} values={snap.values}")
