"""在 tool 内使用 interrupt(): tool 被执行时暂停等待审批, resume 值可覆盖入参。

要点:
- 审批逻辑与 tool 绑在一起, 便于在 graph 各处复用。
- resume 传入的 dict 可以覆盖 to / subject / body 后再真正执行。

运行: python interrupt_in_tool.py
"""

from typing import TypedDict

from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


@tool
def send_email(to: str, subject: str, body: str) -> str:
    """Send an email to a recipient."""
    # 发送前暂停; payload 会出现在 result["__interrupt__"] (invoke) 或 stream.interrupts
    response = interrupt(
        {
            "action": "send_email",
            "to": to,
            "subject": subject,
            "body": body,
            "message": "Approve sending this email?",
        }
    )

    if response.get("action") == "approve":
        # resume 值可在执行前覆盖入参
        final_to = response.get("to", to)
        final_subject = response.get("subject", subject)
        return f"Email sent to {final_to} with subject '{final_subject}'"
    return "Email cancelled by user"


class AgentState(TypedDict):
    result: str


def tool_node(state: AgentState):
    # 真实场景中该 tool 由 LLM 触发; 这里直接调用以最小化依赖
    observation = send_email.invoke(
        {"to": "alice@example.com", "subject": "Meeting", "body": "See you at 3pm"}
    )
    return {"result": observation}


builder = StateGraph(AgentState)
builder.add_node("tool_node", tool_node)
builder.add_edge(START, "tool_node")
builder.add_edge("tool_node", END)

graph = builder.compile(checkpointer=InMemorySaver())

config = {"configurable": {"thread_id": "email-workflow"}}

initial = graph.invoke({"result": ""}, config)
print("interrupts:", initial["__interrupt__"])
# -> (Interrupt(value={'action': 'send_email', ...}),)

# 批准, 并顺带修改 subject
resumed = graph.invoke(
    Command(resume={"action": "approve", "subject": "Updated subject"}), config
)
print("result:", resumed["result"])
# -> Email sent to alice@example.com with subject 'Updated subject'
