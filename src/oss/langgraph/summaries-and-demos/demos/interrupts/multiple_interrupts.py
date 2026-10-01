"""并行分支同时 interrupt: 用 {interrupt_id: resume_value} 映射一次性恢复多个。

要点:
- 单值 resume 只对应单个 interrupt; 多 interrupt 必须按 ID 配对。
- interrupt 的匹配严格基于索引, 因此 node 内 interrupt 调用顺序必须稳定。

运行: python multiple_interrupts.py
"""

import operator
from typing import Annotated, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


class State(TypedDict):
    vals: Annotated[list[str], operator.add]


def node_a(state):
    answer = interrupt("question_a")
    return {"vals": [f"a:{answer}"]}


def node_b(state):
    answer = interrupt("question_b")
    return {"vals": [f"b:{answer}"]}


graph = (
    StateGraph(State)
    .add_node("a", node_a)
    .add_node("b", node_b)
    .add_edge(START, "a")
    .add_edge(START, "b")
    .add_edge("a", END)
    .add_edge("b", END)
    .compile(checkpointer=InMemorySaver())
)

config = {"configurable": {"thread_id": "1"}}

# 1. 首次运行: 两个并行 node 同时命中 interrupt() 并暂停
result = graph.invoke({"vals": []}, config)
print("interrupts:", result["__interrupt__"])
# -> (Interrupt(value='question_a', id='...'), Interrupt(value='question_b', id='...'))

# 2. 一次性恢复所有 pending interrupt: 把每个 id 映射到它的 resume 值
resume_map = {i.id: f"answer for {i.value}" for i in result["__interrupt__"]}
final = graph.invoke(Command(resume=resume_map), config)

print("final:", final["vals"])
# -> ['a:answer for question_a', 'b:answer for question_b']
