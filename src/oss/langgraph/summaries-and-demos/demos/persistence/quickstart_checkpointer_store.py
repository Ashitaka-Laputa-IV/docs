"""Persistence 快速开始: 用一个 checkpointer + 一个 store 编译 graph。

对应 persistence.mdx「快速开始」。
- checkpointer: short-term, thread 作用域, 靠 config 里的 thread_id 存取。
- store: long-term, 跨 thread, 从 node 中通过 runtime.store 读写。
"""

from typing import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.store.memory import InMemoryStore


class State(TypedDict):
    messages: list[dict]


def echo(state: State):
    # 真实应用里这里通常调用 LLM; 此处只回显, 保持示例可独立运行。
    last = state["messages"][-1]
    return {"messages": [{"role": "assistant", "content": f"echo: {last['content']}"}]}


def main() -> None:
    checkpointer = InMemorySaver()
    store = InMemoryStore()

    builder = StateGraph(State)
    builder.add_node("echo", echo)
    builder.add_edge(START, "echo")
    builder.add_edge("echo", END)

    graph = builder.compile(checkpointer=checkpointer, store=store)

    config = {"configurable": {"thread_id": "thread-1"}}

    # 第一次调用
    result = graph.invoke(
        {"messages": [{"role": "user", "content": "Hi, my name is Bob."}]},
        config,
    )
    print("第一次:", result["messages"][-1]["content"])

    # 同一个 thread 再调一次: checkpointer 让 state 累积保留
    result = graph.invoke(
        {"messages": [{"role": "user", "content": "what's my name?"}]},
        config,
    )
    print("第二次调用后 thread 内共", len(result["messages"]), "条消息:")
    for m in result["messages"]:
        print(" ", m["role"], "->", m["content"])

    # 查看保存的 state snapshot
    snapshot = graph.get_state(config)
    print("最新 checkpoint_id:", snapshot.config["configurable"]["checkpoint_id"])
    print("next:", snapshot.next, "(空表示 graph 已完成)")


if __name__ == "__main__":
    main()
