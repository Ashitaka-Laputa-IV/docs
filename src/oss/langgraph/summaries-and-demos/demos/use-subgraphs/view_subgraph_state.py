"""查看 subgraph state: 用 get_state(config, subgraphs=True)。

要点:
- 前提: subgraph 必须能被 LangGraph 静态发现 (作为 node 添加 / 在 node 内调用)。
  若藏在 tool 函数或间接层里, 查看功能不生效 (但 interrupt 仍会传播到顶层)。
- 按调用 (默认): 仅返回当前调用的 subgraph state (interrupt 期间)。
- 按 thread (checkpointer=True): 返回该 thread 上累积的 state。

运行: python view_subgraph_state.py
"""

from typing import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, StateGraph
from langgraph.types import Command, interrupt


class State(TypedDict):
    foo: str


def subgraph_node_1(state: State):
    value = interrupt("Provide value:")
    return {"foo": state["foo"] + value}


subgraph_builder = StateGraph(State)
subgraph_builder.add_node("subgraph_node_1", subgraph_node_1)
subgraph_builder.add_edge(START, "subgraph_node_1")
subgraph = subgraph_builder.compile()  # 继承父 checkpointer


builder = StateGraph(State)
builder.add_node("node_1", subgraph)
builder.add_edge(START, "node_1")
graph = builder.compile(checkpointer=InMemorySaver())

config = {"configurable": {"thread_id": "1"}}

graph.invoke({"foo": ""}, config)

# 查看当前调用的 subgraph state
subgraph_state = graph.get_state(config, subgraphs=True).tasks[0].state
print("subgraph state:", subgraph_state.values)

# 恢复 subgraph
final = graph.invoke(Command(resume="bar"), config)
print("final:", final)
