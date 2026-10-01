"""event-streaming.mdx: 在 interrupt 之后检查并恢复。

graph 为等待人工输入而暂停时:
1. 检查 stream.interrupted / stream.interrupts
2. 再次调用 stream_events 并传入 Command(resume=...) 恢复

恢复要求 graph 用 checkpointer 编译, 且 config 携带 thread ID。

依赖: pip install langgraph
运行: python resume_after_interrupt.py
"""

from typing import TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


class State(TypedDict):
    decisions: list


def approval_node(state: State):
    # 在此暂停, 等待人工输入
    decision = interrupt({"question": "Approve this action?", "options": ["approve", "reject"]})
    return {"decisions": [decision]}


def finalize_node(state: State):
    return state


builder = StateGraph(State)
builder.add_node("approval", approval_node)
builder.add_node("finalize", finalize_node)
builder.add_edge(START, "approval")
builder.add_edge("approval", "finalize")
builder.add_edge("finalize", END)
graph = builder.compile(checkpointer=MemorySaver())

config = {"configurable": {"thread_id": "thread-1"}}

if __name__ == "__main__":
    stream = graph.stream_events({"decisions": []}, config, version="v3")

    if stream.interrupted:
        print("interrupts:", stream.interrupts)

        # 恢复: 传入 Command
        stream = graph.stream_events(
            Command(resume={"decisions": [{"type": "approve"}]}),
            config,
            version="v3",
        )

    final_state = stream.output
    print("final_state:", final_state)
