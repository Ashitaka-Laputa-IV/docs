"""Human-in-the-loop: interrupt() 暂停 + 恢复的最小可运行示例。

对应 thinking-in-langgraph Step 5 "试用你的 agent" (源码页引用的 HITL snippet)。
不依赖任何 LLM / API key, 可直接运行: python hitl_interrupt_demo.py

要点:
- 用 interrupt() 暂停执行, state 被完整保存到 checkpointer。
- 必须 compile(checkpointer=...) 且 invoke 时传 thread_id。
- 用 Command(resume=...) 从中断处**精确**恢复。
"""

from typing import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


class EmailState(TypedDict):
    email_content: str
    response_text: str | None


def human_review_node(state: EmailState):
    # interrupt() 必须放在函数最前面: 之前的代码在恢复时会重新运行。
    decision = interrupt(
        {
            "approved": False,
            "edited_response": state.get("response_text") or "",
            "action": "Please review and approve/edit this response",
        }
    )
    return {"response_text": decision.get("edited_response", state.get("response_text"))}


def send_reply_node(state: EmailState):
    print(f"Sending reply: {state['response_text'][:100]}...")
    return {}


app = (
    StateGraph(EmailState)
    .add_node("human_review", human_review_node)
    .add_node("send_reply", send_reply_node)
    .add_edge(START, "human_review")
    .add_edge("human_review", "send_reply")
    .add_edge("send_reply", END)
    .compile(checkpointer=InMemorySaver())
)


if __name__ == "__main__":
    initial_state: EmailState = {
        "email_content": "I was charged twice for my subscription! This is urgent!",
        "response_text": "Draft response",
    }

    # thread_id 确保该会话的所有 state 保存在一起
    config = {"configurable": {"thread_id": "customer_123"}}

    # 第一次运行会在 human_review 处暂停
    app.invoke(initial_state, config)
    snapshot = app.get_state(config)
    print("待处理的 interrupt:", snapshot.tasks[0].interrupts)

    # 提供人工输入后恢复
    human_response = Command(
        resume={
            "approved": True,
            "edited_response": "We sincerely apologize for the double charge. "
            "I've initiated an immediate refund...",
        }
    )
    app.invoke(human_response, config)
    print("Email sent successfully!")
