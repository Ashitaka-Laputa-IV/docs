"""fault-tolerance.mdx: 基础重试策略。

把 retry_policy= 传给 add_node。默认 retry_on 会对任何异常重试,
但排除 ValueError/TypeError/RuntimeError 等 (及其子类); HTTP 库只重试 5xx。

依赖: pip install langgraph
运行: python retry_policy.py
"""

from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy

_attempts = {"n": 0}


class State(TypedDict):
    result: str


def call_api(state: State):
    """前两次抛瞬时错误, 第三次成功 (模拟临时网络故障)。"""
    _attempts["n"] += 1
    if _attempts["n"] < 3:
        raise ConnectionError(f"transient network error (attempt {_attempts['n']})")
    return {"result": "ok"}


builder = StateGraph(State)
builder.add_node(
    "call_api",
    call_api,
    retry_policy=RetryPolicy(max_attempts=3),   # 最多尝试 3 次 (含第一次)
)
builder.add_edge(START, "call_api")
builder.add_edge("call_api", END)
graph = builder.compile()


if __name__ == "__main__":
    print(graph.invoke({"result": ""}))
    print(f"total attempts: {_attempts['n']}")
