"""Time travel 遇上 interrupts: interrupt 总会被重新触发。

要点:
- 若 graph 用 interrupt() 做 HITL, 重放/分叉时包含该 interrupt 的 node 会重跑,
  interrupt() 再次暂停, 等待一个新的 Command(resume=...)。
- 可以从两个 interrupt 之间分叉, 从而改后续答案而不重问先前问题。

运行: python time_travel_with_interrupts.py
"""

from typing import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, StateGraph
from langgraph.types import Command, interrupt


class State(TypedDict):
    value: list[str]


def ask_human(state: State):
    answer = interrupt("What is your name?")
    return {"value": [f"Hello, {answer}!"]}


def final_step(state: State):
    return {"value": ["Done"]}


graph = (
    StateGraph(State)
    .add_node("ask_human", ask_human)
    .add_node("final_step", final_step)
    .add_edge(START, "ask_human")
    .add_edge("ask_human", "final_step")
    .compile(checkpointer=InMemorySaver())
)

config = {"configurable": {"thread_id": "1"}}

# 首次运行: 命中 interrupt; 再用 Alice 恢复
graph.invoke({"value": []}, config)
graph.invoke(Command(resume="Alice"), config)

# 从 ask_human 之前重放
history = list(graph.get_state_history(config))
before_ask = [s for s in history if s.next == ("ask_human",)][-1]

replay_result = graph.invoke(None, before_ask.config)
# 再次暂停在 interrupt, 等待新的 Command(resume=...)
print("replay interrupts:", replay_result["__interrupt__"])

# 从 ask_human 之前分叉
fork_config = graph.update_state(before_ask.config, {"value": ["forked"]})
fork_result = graph.invoke(None, fork_config)
print("fork interrupts:", fork_result["__interrupt__"])

# 用不同答案恢复分叉出的 interrupt
final = graph.invoke(Command(resume="Bob"), fork_config)
print("fork final:", final["value"])
# -> ['forked', 'Hello, Bob!', 'Done']
