"""streaming.mdx: checkpoints / tasks / debug 三种 stream mode。

- checkpoints: 每个 checkpoint 事件, 格式同 get_state()  —— 需要 checkpointer
- tasks      : node 的启动/完成事件, 含结果与错误        —— 需要 checkpointer
- debug      : checkpoints + tasks + 额外 metadata (超集)

依赖: pip install langgraph
运行: python checkpoints_tasks_debug.py
"""

from typing import TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph


class State(TypedDict):
    topic: str
    joke: str


def refine_topic(state: State):
    return {"topic": state["topic"] + " and cats"}


def generate_joke(state: State):
    return {"joke": f"This is a joke about {state['topic']}"}


def build_graph(with_checkpointer: bool = True):
    builder = (
        StateGraph(State)
        .add_node(refine_topic)
        .add_node(generate_joke)
        .add_edge(START, "refine_topic")
        .add_edge("refine_topic", "generate_joke")
        .add_edge("generate_joke", END)
    )
    return builder.compile(checkpointer=MemorySaver()) if with_checkpointer else builder.compile()


config = {"configurable": {"thread_id": "1"}}


if __name__ == "__main__":
    graph = build_graph()

    print("=== checkpoints ===")
    for chunk in graph.stream(
        {"topic": "ice cream"}, config=config, stream_mode="checkpoints", version="v2"
    ):
        if chunk["type"] == "checkpoints":
            print(chunk["data"])

    print("\n=== tasks ===")
    for chunk in graph.stream(
        {"topic": "ice cream"}, config=config, stream_mode="tasks", version="v2"
    ):
        if chunk["type"] == "tasks":
            print(chunk["data"])

    print("\n=== debug ===")
    for chunk in graph.stream(
        {"topic": "ice cream"}, config=config, stream_mode="debug", version="v2"
    ):
        if chunk["type"] == "debug":
            print(chunk["data"])
