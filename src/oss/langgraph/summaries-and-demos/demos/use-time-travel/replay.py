"""Time travel - 重放 (replay): 用旧 checkpoint 的 config 重新调用 graph。

要点:
- 重放是真正重新执行 node, 不是读缓存; LLM/API/interrupt 会再次触发。
- checkpoint 之前的 node 不重跑, 之后的 node 重跑。
- get_state_history 返回逆时间序; state.next 表示"接下来要执行的 node"。
- 从最终 checkpoint (无 next) 重放是空操作。

运行: python replay.py
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


checkpointer = InMemorySaver()
graph = (
    StateGraph(State)
    .add_node("generate_topic", generate_topic)
    .add_node("write_joke", write_joke)
    .add_edge(START, "generate_topic")
    .add_edge("generate_topic", "write_joke")
    .compile(checkpointer=checkpointer)
)

# 1. 运行 graph
config = {"configurable": {"thread_id": "1"}}
graph.invoke({}, config)

# 2. 找到要重放的 checkpoint (history 为逆时间序)
history = list(graph.get_state_history(config))
for state in history:
    print(f"next={state.next}, checkpoint_id={state.config['configurable']['checkpoint_id']}")

# 3. 从 write_joke 之前的 checkpoint 重放
before_joke = next(s for s in history if s.next == ("write_joke",))
replay_result = graph.invoke(None, before_joke.config)
# write_joke 重新执行, generate_topic 不执行
print("replayed joke:", replay_result["joke"])
