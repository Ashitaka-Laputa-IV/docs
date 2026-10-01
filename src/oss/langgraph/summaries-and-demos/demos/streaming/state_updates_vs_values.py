"""streaming.mdx: Graph state 的两种 stream 方式对比。

- updates: 每一步之后 state 的增量更新 (只含变化的 key)
- values : 每一步之后 state 的完整快照

依赖: pip install langgraph
运行: python state_updates_vs_values.py
"""

from typing import TypedDict

from langgraph.graph import END, START, StateGraph


class State(TypedDict):
    topic: str
    joke: str


def refine_topic(state: State):
    return {"topic": state["topic"] + " and cats"}


def generate_joke(state: State):
    return {"joke": f"This is a joke about {state['topic']}"}


graph = (
    StateGraph(State)
    .add_node(refine_topic)
    .add_node(generate_joke)
    .add_edge(START, "refine_topic")
    .add_edge("refine_topic", "generate_joke")
    .add_edge("generate_joke", END)
    .compile()
)


def demo_updates() -> None:
    print("=== updates (增量) ===")
    for chunk in graph.stream(
        {"topic": "ice cream"}, stream_mode="updates", version="v2"
    ):
        if chunk["type"] == "updates":
            for node_name, state in chunk["data"].items():
                print(f"Node `{node_name}` updated: {state}")


def demo_values() -> None:
    print("\n=== values (完整快照) ===")
    for chunk in graph.stream(
        {"topic": "ice cream"}, stream_mode="values", version="v2"
    ):
        if chunk["type"] == "values":
            print(f"topic: {chunk['data']['topic']}, joke: {chunk['data']['joke']}")


if __name__ == "__main__":
    demo_updates()
    demo_values()
    # updates:
    # Node `refine_topic` updated: {'topic': 'ice cream and cats'}
    # Node `generate_joke` updated: {'joke': 'This is a joke about ice cream and cats'}
    # values:
    # topic: ice cream, joke:
    # topic: ice cream and cats, joke:
    # topic: ice cream and cats, joke: This is a joke about ice cream and cats
