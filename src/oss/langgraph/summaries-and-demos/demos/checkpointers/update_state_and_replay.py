"""update_state 与重放(replay)演示。

对应 checkpointers.mdx「重放」与「更新 state」。

要点:
- update_state 不改原始 checkpoint, 而是新建一个 checkpoint;
- 带 reducer 的通道会累积而非覆盖;
- 重放: 用旧 checkpoint_id 调用 graph, 会重新执行该 checkpoint 之后的 node
  (之前的 node 被跳过, 之后的有副作用 node 会被重新触发)。
"""

from operator import add
from typing import Annotated

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

RUNS = {"node_b": 0}


class State(TypedDict):
    foo: str
    bar: Annotated[list[str], add]


def node_a(state: State):
    return {"foo": "a", "bar": ["a"]}


def node_b(state: State):
    RUNS["node_b"] += 1
    print(f"  [node_b 执行第 {RUNS['node_b']} 次]")
    return {"foo": "b", "bar": ["b"]}


def main() -> None:
    workflow = StateGraph(State)
    workflow.add_node(node_a)
    workflow.add_node(node_b)
    workflow.add_edge(START, "node_a")
    workflow.add_edge("node_a", "node_b")
    workflow.add_edge("node_b", END)

    graph = workflow.compile(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "1"}}

    print("第一次完整执行:")
    graph.invoke({"foo": "", "bar": []}, config)
    print("  values:", graph.get_state(config).values)

    # --- 更新 state: 新建 checkpoint, 不改原始 ---
    print("\nupdate_state(foo='patched'):")
    new_config = graph.update_state(config, {"foo": "patched"})
    print("  更新后 values:", graph.get_state(config).values)
    print("  新 checkpoint_id:", new_config["configurable"]["checkpoint_id"])
    print("  (原始 checkpoint 仍在历史中, 未被修改)")

    # --- 重放: 回到 node_b 执行之前的 checkpoint ---
    history = list(graph.get_state_history(config))
    before_node_b = next(s for s in history if s.next == ("node_b",))
    print("\n从 node_b 之前的 checkpoint 重放:")
    print("  重放起点 values:", before_node_b.values)
    graph.invoke(None, before_node_b.config)  # node_a 被跳过, node_b 重新执行
    print("  重放后 values:", graph.get_state(config).values)

    print("\n注意: 重放会重新触发 checkpoint 之后的 node(含 LLM / API 等副作用)。")


if __name__ == "__main__":
    main()
