"""审批工作流: 关键操作前 interrupt 暂停, 依据审批结果路由到 proceed / cancel。

要点:
- 返回类型标注 Command[Literal["proceed", "cancel"]] 便于路由与类型检查。
- 恢复时传 True 表示批准, False 表示拒绝。

运行: python approval_routing.py
"""

from typing import Literal, Optional, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


class ApprovalState(TypedDict):
    action_details: str
    status: Optional[Literal["pending", "approved", "rejected"]]


def approval_node(state: ApprovalState) -> Command[Literal["proceed", "cancel"]]:
    # 把详情暴露给调用方, 便于 UI 渲染
    decision = interrupt(
        {
            "question": "Approve this action?",
            "details": state["action_details"],
        }
    )
    # 恢复后按决策路由
    return Command(goto="proceed" if decision else "cancel")


def proceed_node(state: ApprovalState):
    return {"status": "approved"}


def cancel_node(state: ApprovalState):
    return {"status": "rejected"}


builder = StateGraph(ApprovalState)
builder.add_node("approval", approval_node)
builder.add_node("proceed", proceed_node)
builder.add_node("cancel", cancel_node)
builder.add_edge(START, "approval")
builder.add_edge("proceed", END)
builder.add_edge("cancel", END)

graph = builder.compile(checkpointer=InMemorySaver())

config = {"configurable": {"thread_id": "approval-123"}}

initial = graph.invoke(
    {"action_details": "Transfer $500", "status": "pending"}, config
)
print("interrupts:", initial["__interrupt__"])

# 恢复: True -> proceed, False -> cancel
resumed = graph.invoke(Command(resume=True), config)
print("status:", resumed["status"])  # -> approved
