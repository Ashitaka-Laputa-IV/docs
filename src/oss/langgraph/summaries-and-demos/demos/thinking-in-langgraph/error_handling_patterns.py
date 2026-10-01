"""四种错误处理策略的最小可运行示例 (thinking-in-langgraph Step 4.1)。

对照文档表格:
- 瞬时错误        -> RetryPolicy 自动重试
- LLM 可恢复      -> 把错误写进 state 并回环 (Command goto)
- 用户可修复      -> interrupt() 暂停等待输入
- 意料之外        -> 向上抛出
- 重试后仍失败的  -> error_handler 补偿 (Saga)

运行: python error_handling_patterns.py
"""

from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, RetryPolicy


class State(TypedDict):
    tool_call: dict
    tool_result: str
    attempts: int


# ---------------------------------------------------------------------------
# 1) 瞬时错误: RetryPolicy 自动重试 (失败几次后成功)
# ---------------------------------------------------------------------------
_flaky_counter = {"n": 0}


def flaky_search(state: State) -> dict:
    """模拟一个前两次失败、第三次成功的外部调用。"""
    _flaky_counter["n"] += 1
    if _flaky_counter["n"] < 3:
        raise ConnectionError(f"transient failure #{_flaky_counter['n']}")
    return {"tool_result": "search ok"}


# ---------------------------------------------------------------------------
# 2) LLM 可恢复错误: 把错误结果写回 state 并回环给 agent
# ---------------------------------------------------------------------------
def execute_tool(state: State) -> Command[Literal["agent"]]:
    """tool 失败时不让异常冒泡, 而是把错误文本交给 LLM 重试。"""
    try:
        if state["tool_call"].get("should_fail"):
            raise ValueError("bad arguments")
        result = "tool ok"
    except ValueError as e:
        # 让 LLM 看到错在哪里并调整做法
        return Command(update={"tool_result": f"Tool error: {e}"}, goto="agent")
    return Command(update={"tool_result": result}, goto="agent")


def agent(state: State) -> dict:
    return {"tool_result": state.get("tool_result", "")}


def build_retry_graph():
    workflow = StateGraph(State)
    workflow.add_node(
        "search",
        flaky_search,
        retry_policy=RetryPolicy(max_attempts=3, initial_interval=0.1),
    )
    workflow.add_edge(START, "search")
    workflow.add_edge("search", END)
    return workflow.compile()


def build_llm_recoverable_graph():
    workflow = StateGraph(State)
    workflow.add_node("agent", agent)
    workflow.add_node("execute_tool", execute_tool)
    workflow.add_edge(START, "execute_tool")
    return workflow.compile()


if __name__ == "__main__":
    # 瞬时错误: 前两次抛错, 重试后成功
    app = build_retry_graph()
    result = app.invoke({"tool_call": {}, "tool_result": "", "attempts": 0})
    print("[retry] 结果:", result["tool_result"])

    # LLM 可恢复: 错误被当作结果回环
    app2 = build_llm_recoverable_graph()
    result2 = app2.invoke(
        {"tool_call": {"should_fail": True}, "tool_result": "", "attempts": 0}
    )
    print("[llm-recoverable] 结果:", result2["tool_result"])
