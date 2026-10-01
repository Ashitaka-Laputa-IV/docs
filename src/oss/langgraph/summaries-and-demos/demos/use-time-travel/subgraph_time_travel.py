"""对 subgraph 做 time travel: 用 subgraph 自己的 checkpointer 分叉到内部点。

要点:
- subgraph 默认继承父 checkpointer, 父级视其为单个 super-step:
  无法 time travel 到 subgraph 内部 node 之间。
- 给 subgraph 设 checkpointer=True 后, 它拥有自己的 checkpoint 历史,
  可从内部某点 (如两个 interrupt 之间) time travel。
- 用 graph.get_state(config, subgraphs=True).tasks[0].state.config 拿到 subgraph 的 config。

运行: python subgraph_time_travel.py
"""

from typing import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


class State(TypedDict):
    value: list[str]


def step_a(state: State):
    name = interrupt("What is your name?")
    return {"value": [f"name:{name}"]}


def step_b(state: State):
    age = interrupt("How old are you?")
    return {"value": [f"age:{age}"]}


# subgraph 拥有自己的 checkpoint 历史 (checkpointer=True)
subgraph = (
    StateGraph(State)
    .add_node("step_a", step_a)
    .add_node("step_b", step_b)
    .add_edge(START, "step_a")
    .add_edge("step_a", "step_b")
    .compile(checkpointer=True)
)

graph = (
    StateGraph(State)
    .add_node("subgraph_node", subgraph)
    .add_edge(START, "subgraph_node")
    .compile(checkpointer=InMemorySaver())
)

config = {"configurable": {"thread_id": "1"}}

# 运行到 step_a interrupt, 再用 Alice 恢复 -> 命中 step_b interrupt
graph.invoke({"value": []}, config)
graph.invoke(Command(resume="Alice"), config)

# 拿到 subgraph 自己的 checkpoint (step_a 与 step_b 之间)
parent_state = graph.get_state(config, subgraphs=True)
sub_config = parent_state.tasks[0].state.config
print("subgraph state:", parent_state.tasks[0].state.values)

# 从 subgraph checkpoint 分叉
fork_config = graph.update_state(sub_config, {"value": ["forked"]})
result = graph.invoke(None, fork_config)
# step_b 重新执行, step_a 的结果被保留
print("fork result:", result.get("value"))
print("interrupts:", result.get("__interrupt__"))
