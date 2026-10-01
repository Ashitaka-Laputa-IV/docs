"""在 state 历史中筛选特定 checkpoint。

对应 checkpointers.mdx「查找特定的 checkpoint」。

演示四类常见筛选:
- 某个 node 执行之前的 checkpoint
- 按 super-step 号查找
- 由 update_state 产生的分叉 checkpoint
- 发生 interrupt 的 checkpoint
"""

from operator import add
from typing import Annotated

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict


class State(TypedDict):
    foo: str
    bar: Annotated[list[str], add]


def node_a(state: State):
    return {"foo": "a", "bar": ["a"]}


def node_b(state: State):
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
    graph.invoke({"foo": "", "bar": []}, config)

    # 制造一个 source="update" 的 checkpoint, 便于演示分叉筛选
    graph.update_state(config, {"foo": "patched"})

    history = list(graph.get_state_history(config))

    # 1) node_b 执行之前的 checkpoint
    before_node_b = next(s for s in history if s.next == ("node_b",))
    print("node_b 之前的 checkpoint:", before_node_b.values)

    # 2) 按 step 号查找
    step_2 = next(s for s in history if s.metadata["step"] == 2)
    print("step == 2 的 checkpoint:", step_2.values)

    # 3) update_state 产生的分叉
    forks = [s for s in history if s.metadata["source"] == "update"]
    print("update 分叉数量:", len(forks))
    for s in forks:
        print("  分叉 values:", s.values)

    # 4) 发生 interrupt 的 checkpoint(本 demo 无 interrupt, 应为空)
    interrupted = [
        s for s in history if s.tasks and any(t.interrupts for t in s.tasks)
    ]
    print("发生 interrupt 的 checkpoint:", interrupted)


if __name__ == "__main__":
    main()
