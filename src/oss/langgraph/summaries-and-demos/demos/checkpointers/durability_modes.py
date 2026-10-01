"""持久性(durability)模式: exit / async / sync。

对应 checkpointers.mdx「持久性模式」。
- "exit": 只在 graph 执行退出时持久化, 性能最好, 但中途崩溃无法恢复。
- "async": 下一步执行时异步持久化, 性能与持久性折中。
- "sync": 下一步开始前同步持久化, 持久性最高, 有一定性能开销。
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


def build_graph():
    workflow = StateGraph(State)
    workflow.add_node(node_a)
    workflow.add_node(node_b)
    workflow.add_edge(START, "node_a")
    workflow.add_edge("node_a", "node_b")
    workflow.add_edge("node_b", END)
    return workflow.compile(checkpointer=InMemorySaver())


def main() -> None:
    for mode in ("exit", "async", "sync"):
        graph = build_graph()
        config = {"configurable": {"thread_id": f"thread-{mode}"}}
        # durability 在调用 graph 执行方法时指定
        for _ in graph.stream({"foo": "", "bar": []}, config, durability=mode):
            pass
        print(f"durability={mode:<5} 最终 values:", graph.get_state(config).values)


if __name__ == "__main__":
    main()
