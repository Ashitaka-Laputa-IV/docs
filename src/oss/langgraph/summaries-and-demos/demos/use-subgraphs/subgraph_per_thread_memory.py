"""按 thread persistence (checkpointer=True): subgraph state 跨多次调用累积。

要点:
- 默认 (None) 是"按调用": 每次调用从头开始, subagent 不记得先前调用。
- checkpointer=True 让 subgraph 在同一 thread 上累积 state, 每次从上次离开处继续。
- checkpointer=False 则完全无 checkpoint (无 interrupt / 无持久化执行)。

运行: python subgraph_per_thread_memory.py
"""

import operator
from typing import Annotated, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph


# ---------- Subgraph 拥有自己的按 thread 历史 ----------
class SubState(TypedDict):
    items: Annotated[list[str], operator.add]


def respond(state: SubState):
    # 记录"到目前为止我见过多少条" —— 按 thread 模式下该计数会累积
    return {"items": [f"seen {len(state['items'])} items so far"]}


sub_builder = StateGraph(SubState)
sub_builder.add_node("respond", respond)
sub_builder.add_edge(START, "respond")
sub_builder.add_edge("respond", END)
subgraph = sub_builder.compile(checkpointer=True)  # 拥有自己的 thread 级历史


# ---------- Parent graph ----------
class ParentState(TypedDict):
    items: Annotated[list[str], operator.add]


builder = StateGraph(ParentState)
builder.add_node("agent", subgraph)
builder.add_edge(START, "agent")
builder.add_edge("agent", END)
graph = builder.compile(checkpointer=InMemorySaver())

config = {"configurable": {"thread_id": "1"}}

graph.invoke({"items": ["first"]}, config)
r2 = graph.invoke({"items": ["second"]}, config)
print("accumulated items:", r2["items"])
# 因 checkpointer=True, subgraph 记住了上一次调用 (计数递增)
