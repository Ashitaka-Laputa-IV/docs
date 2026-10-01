"""校验人工输入的正确模式: 一次 interrupt() + conditional edge 回环。

反例警告:
    绝不要在单个 node 内写 `while True: interrupt(...)` 校验循环。
    因为恢复时 node 会从头重跑, 每次恢复都会重放之前所有迭代,
    循环体代码会被指数级重复执行。

正确做法:
    1. 把重新提示的问题存入 state (pending_question)
    2. node 中恰好调用一次 interrupt(), 传入来自 state 的当前问题
    3. 无效则返回更新后的 pending_question
    4. 用 add_conditional_edges 回环到该 node, 直到拿到有效值

运行: python validate_human_input.py
"""

from typing import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


class FormState(TypedDict):
    age: int | None
    pending_question: str | None


def get_age_node(state: FormState):
    question = state.get("pending_question") or "What is your age?"
    answer = interrupt(question)  # 每次 node 调用恰好一次
    print(f"I got {answer}")  # 每次 resume 恰好运行一次

    if isinstance(answer, int) and answer > 0:
        return {"age": answer, "pending_question": None}
    return {
        "pending_question": f"'{answer}' is not a valid age. Please enter a positive number."
    }


def route(state: FormState):
    # 未拿到有效值就回环到 collect_age
    return END if state.get("age") is not None else "collect_age"


builder = StateGraph(FormState)
builder.add_node("collect_age", get_age_node)
builder.add_edge(START, "collect_age")
builder.add_conditional_edges("collect_age", route)

graph = builder.compile(checkpointer=InMemorySaver())

config = {"configurable": {"thread_id": "form-1"}}

first = graph.invoke({"age": None, "pending_question": None}, config)
print("interrupts:", first["__interrupt__"])  # -> What is your age?

# 传无效数据 -> 通过 conditional edge 重新提示
retry = graph.invoke(Command(resume="thirty"), config)
print("interrupts:", retry["__interrupt__"])  # -> "'thirty' is not a valid age..."

# 传有效数据 -> route() 返回 END, graph 结束
final = graph.invoke(Command(resume=30), config)
print("age:", final["age"])  # -> 30
