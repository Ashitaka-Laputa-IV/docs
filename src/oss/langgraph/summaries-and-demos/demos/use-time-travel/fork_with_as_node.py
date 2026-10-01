"""Time travel - 从特定 node 分叉: 用 as_node 显式指定"谁产生了这次更新"。

要点:
- update_state 的值会用指定 node 的 writer 应用 (含 reducers);
  执行从该 node 的后继节点恢复。
- 默认从版本历史推断 as_node; 以下情况需显式指定:
    * 并行分支 (歧义 -> InvalidUpdateError)
    * 全新 thread 无执行历史 (测试场景)
    * 想跳过 node

运行: python fork_with_as_node.py
"""

from typing import NotRequired, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, StateGraph


class State(TypedDict):
    topic: NotRequired[str]
    joke: NotRequired[str]


def generate_topic(state: State):
    return {"topic": "socks in the dryer"}


def write_joke(state: State):
    return {"joke": f"Why do {state['topic']} disappear? They elope!"}


graph = (
    StateGraph(State)
    .add_node("generate_topic", generate_topic)
    .add_node("write_joke", write_joke)
    .add_edge(START, "generate_topic")
    .add_edge("generate_topic", "write_joke")
    .compile(checkpointer=InMemorySaver())
)

config = {"configurable": {"thread_id": "1"}}
graph.invoke({}, config)

history = list(graph.get_state_history(config))
before_joke = next(s for s in history if s.next == ("write_joke",))

# 把这次更新当作是 generate_topic 产出的
# 执行从 generate_topic 的后继 (write_joke) 恢复
fork_config = graph.update_state(
    before_joke.config,
    values={"topic": "chickens"},
    as_node="generate_topic",
)
fork_result = graph.invoke(None, fork_config)
print("forked joke:", fork_result["joke"])
