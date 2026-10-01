"""fault-tolerance.mdx: 自定义重试判断逻辑。

把可调用对象传给 retry_on; 导入 default_retry_on 可扩展默认行为。

依赖: pip install langgraph
运行: python custom_retry_on.py
"""

from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy, default_retry_on

_attempts = {"n": 0}


class MyCustomError(Exception):
    """我们明确不希望重试的业务异常。"""


class State(TypedDict):
    result: str


def custom_retry_on(exc: BaseException) -> bool:
    # 自定义异常不重试, 其余交给默认判断
    if isinstance(exc, MyCustomError):
        return False
    return default_retry_on(exc)


def call_api(state: State):
    _attempts["n"] += 1
    if _attempts["n"] < 2:
        raise ConnectionError("transient")
    return {"result": "ok"}


builder = StateGraph(State)
builder.add_node(
    "call_api",
    call_api,
    retry_policy=RetryPolicy(max_attempts=3, retry_on=custom_retry_on),
)
builder.add_edge(START, "call_api")
builder.add_edge("call_api", END)
graph = builder.compile()


if __name__ == "__main__":
    print(graph.invoke({"result": ""}))
    print(f"total attempts: {_attempts['n']}")
