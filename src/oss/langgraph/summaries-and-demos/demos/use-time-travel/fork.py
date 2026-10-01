"""Time travel - 分叉 (fork): 先 update_state 改过去的 state, 再从该点继续。

要点:
- update_state 不回滚 thread, 而是追加一条从该点分出的新 checkpoint; 原始历史保持完整。
- 用 graph.invoke(None, fork_config) 从分叉点继续执行。

运行: python fork.py
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
original = graph.invoke({}, config)
print("original joke:", original["joke"])

# 找到 write_joke 之前的 checkpoint
history = list(graph.get_state_history(config))
before_joke = next(s for s in history if s.next == ("write_joke",))

# 分叉: 修改 topic, 创建一个新分支
fork_config = graph.update_state(before_joke.config, values={"topic": "chickens"})

# 从分叉点继续 -> write_joke 用新 topic 重新执行
fork_result = graph.invoke(None, fork_config)
print("forked joke:", fork_result["joke"])  # 关于 chickens, 而非 socks

# 原始历史仍然完整
original_again = graph.invoke(None, config)
print("original still:", original_again["joke"])
