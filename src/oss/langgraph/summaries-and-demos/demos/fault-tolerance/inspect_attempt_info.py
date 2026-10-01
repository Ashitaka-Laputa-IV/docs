"""fault-tolerance.mdx: 在 node 内查看当前尝试次数 execution_info。

主调用持续失败时, 依据 node_attempt 切换到回退方案。
node_attempt 从 1 开始计数, 第一次重试为 2。

依赖: pip install langgraph
运行: python inspect_attempt_info.py
"""

from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import RetryPolicy


class State(TypedDict):
    result: str


def call_primary_api() -> str:
    raise ConnectionError("primary api down")


def call_fallback_api() -> str:
    return "fallback result"


def my_node(state: State, runtime: Runtime) -> State:
    # 第一次尝试走主 API, 后续重试直接切回退 API
    if runtime.execution_info.node_attempt > 1:
        return {"result": call_fallback_api()}
    return {"result": call_primary_api()}


builder = StateGraph(State)
builder.add_node("my_node", my_node, retry_policy=RetryPolicy(max_attempts=3))
builder.add_edge(START, "my_node")
builder.add_edge("my_node", END)
graph = builder.compile()


if __name__ == "__main__":
    print(graph.invoke({"result": ""}))
    # execution_info 还提供: node_first_attempt_time / thread_id / run_id
    # / checkpoint_id / task_id
