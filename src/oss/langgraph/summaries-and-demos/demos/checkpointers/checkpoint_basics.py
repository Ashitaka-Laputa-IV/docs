"""Checkpointer 基础: super-step 边界如何产生 checkpoint, 以及如何读取。

对应 checkpointers.mdx「核心概念 -> Checkpoints / Super-steps」与「获取 state / 获取 state 历史」。

运行后你会看到：一个 START -> node_a -> node_b -> END 的 graph 总共产生 4 个 checkpoint。
"""

from operator import add
from typing import Annotated

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict


class State(TypedDict):
    foo: str
    # 带 reducer 的通道: 多次写入会累积而不是覆盖
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

    checkpointer = InMemorySaver()
    return workflow.compile(checkpointer=checkpointer)


def main() -> None:
    graph = build_graph()
    config: RunnableConfig = {"configurable": {"thread_id": "1"}}
    graph.invoke({"foo": "", "bar": []}, config)

    # 最新 state
    latest = graph.get_state(config)
    print("最新 values:", latest.values)
    print("最新 next:", latest.next, "(空 tuple 表示已完成)")
    print("metadata:", latest.metadata)

    # 完整历史: 最新的 checkpoint 位于列表首位
    print("\n完整历史(最新在前):")
    for i, snap in enumerate(graph.get_state_history(config)):
        print(
            f"  [{i}] step={snap.metadata['step']:<2} "
            f"source={snap.metadata['source']:<6} "
            f"next={snap.next} values={snap.values}"
        )

    print("\n注意: bar 通道累积了两个 node 的输出 ->", latest.values["bar"])


if __name__ == "__main__":
    main()
