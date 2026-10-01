"""最小 human-in-the-loop 示例: interrupt() 暂停 + Command(resume=...) 恢复。

要点:
- 需要 checkpointer (这里用 InMemorySaver, 生产环境用持久化 checkpointer)。
- 需要 config 里的 thread_id 作为持久化游标。
- 恢复时用同一个 thread_id; resume 值成为 interrupt() 的返回值。

运行: python human_in_the_loop.py
"""

from typing import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


class State(TypedDict):
    approved: bool | None


def approval_node(state: State):
    # 暂停并把 payload 暴露给调用方:
    #   invoke()        -> result["__interrupt__"]
    #   stream_events() -> stream.interrupts / stream.interrupted
    approved = interrupt("Do you approve this action?")

    # 恢复时, Command(resume=...) 传入的值会成为 interrupt() 的返回值。
    # 注意: node 会从头重跑, interrupt() 之前的代码会再次执行。
    return {"approved": approved}


builder = StateGraph(State)
builder.add_node("approval", approval_node)
builder.add_edge(START, "approval")
builder.add_edge("approval", END)

graph = builder.compile(checkpointer=InMemorySaver())

# thread_id 必须与首次运行保持一致才能恢复同一个 checkpoint
config = {"configurable": {"thread_id": "thread-1"}}

# 1. 首次运行: 命中 interrupt 并暂停
result = graph.invoke({"approved": None}, config)
print("interrupts:", result["__interrupt__"])  # -> (Interrupt(value='Do you approve this action?'),)

# 2. 恢复: resume 值成为 interrupt() 的返回值
result = graph.invoke(Command(resume=True), config)
print("final:", result)  # -> {'approved': True}
