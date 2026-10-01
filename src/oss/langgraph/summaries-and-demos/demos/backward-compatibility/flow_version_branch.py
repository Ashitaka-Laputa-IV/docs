"""业务兼容性: 用 state 上的 "行为版本" 做分支 (backward-compatibility)。

场景: 在 triage 与 respond 之间插入新的 policy_check 步骤。
- 已越过 triage 的旧 thread 应直接到 respond (旧流程)。
- 新 thread 从 intake 开始, 被打上 flow_version=2, 走含 policy_check 的新路径。

关键约束: 版本必须在 **thread 启动时**、在任何需要版本化的分支之前设置。
本 demo 不依赖 LLM, 可直接运行: python flow_version_branch.py
"""

from typing import NotRequired, TypedDict

from langgraph.graph import END, START, StateGraph


class State(TypedDict):
    request: str
    flow_version: NotRequired[int]
    response: NotRequired[str]


def intake(state: State) -> dict:
    # 给新 thread 打上当前流程版本; 已越过 intake 的旧 thread 保留已保存的值。
    return {"flow_version": state.get("flow_version", 2)}


def triage(state: State) -> dict:
    return {"response": f"[triage] {state['request']}"}


def policy_check(state: State) -> dict:
    return {"response": state.get("response", "") + " -> [policy_check]"}


def respond(state: State) -> dict:
    return {"response": state.get("response", "") + " -> [respond]"}


def after_triage(state: State) -> str:
    if state.get("flow_version", 1) >= 2:
        return "policy_check"
    return "respond"


builder = StateGraph(State)
builder.add_node("intake", intake)
builder.add_node("triage", triage)
builder.add_node("policy_check", policy_check)
builder.add_node("respond", respond)

builder.add_edge(START, "intake")
builder.add_edge("intake", "triage")
builder.add_conditional_edges("triage", after_triage, ["policy_check", "respond"])
builder.add_edge("policy_check", "respond")
builder.add_edge("respond", END)

graph = builder.compile()


if __name__ == "__main__":
    # 新 thread: 未带 flow_version -> intake 打上 2 -> 走 policy_check
    new_thread = graph.invoke({"request": "reset password"})
    print("新 thread:", new_thread["response"])

    # 模拟旧 thread: 带着旧版本 (1) 在 triage 之后恢复 -> 跳过 policy_check
    legacy_thread = graph.invoke({"request": "reset password", "flow_version": 1})
    print("旧 thread:", legacy_thread["response"])
