"""管理 checkpoints: 查看 thread state / 历史, 以及删除整个 thread。

对应 add-memory.mdx「管理 checkpoints」。
不需要 API key。
"""

from typing import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, StateGraph


class State(TypedDict):
    count: int


def step(state: State):
    return {"count": state.get("count", 0) + 1}


def main() -> None:
    builder = StateGraph(State)
    builder.add_node("step", step)
    builder.add_edge(START, "step")

    checkpointer = InMemorySaver()
    graph = builder.compile(checkpointer=checkpointer)

    config = {"configurable": {"thread_id": "1"}}
    graph.invoke({"count": 0}, config)
    graph.invoke({"count": 0}, config)  # count 会累积到 2

    # --- 查看 thread state ---
    snapshot = graph.get_state(config)
    print("最新 state:", snapshot.values)
    print("最新 checkpoint_id:", snapshot.config["configurable"]["checkpoint_id"])
    print("next:", snapshot.next, "| metadata:", snapshot.metadata)

    # 也可以按 checkpointer API 拿到原始 CheckpointTuple
    tup = checkpointer.get_tuple(config)
    print("checkpointer.get_tuple -> checkpoint id:", tup.checkpoint["id"])

    # --- 查看 thread 历史(最新在前) ---
    print("\n历史:")
    for i, snap in enumerate(graph.get_state_history(config)):
        print(f"  [{i}] step={snap.metadata['step']} values={snap.values}")

    # --- 删除某个 thread 的所有 checkpoints ---
    checkpointer.delete_thread("1")
    print("\n删除 thread 后, 历史条数:", len(list(checkpointer.list(config))))


if __name__ == "__main__":
    main()
