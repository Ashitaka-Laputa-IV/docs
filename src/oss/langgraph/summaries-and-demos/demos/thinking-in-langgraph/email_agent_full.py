"""完整的客服邮件 agent (thinking-in-langgraph 全篇贯通示例)。

包含: 7 个 node (读取/分类/检索/建单/起草/人工审批/发送)、
node 内部路由 (Command)、错误重试 (RetryPolicy)、
human-in-the-loop (interrupt)、checkpointer + thread_id。

依赖: pip install langgraph langchain langchain-deepseek python-dotenv
API key: 自动读取仓库根目录的 .env (DEEPSEEK_API_KEY / SILICONFLOW_API_KEY / LANGSMITH_API_KEY)
运行: python email_agent_full.py
"""

from typing import Literal, TypedDict

from dotenv import load_dotenv

load_dotenv()  # 自动向上查找仓库根目录的 .env

from langchain.chat_models import init_chat_model
from langchain.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, RetryPolicy, interrupt

llm = init_chat_model("deepseek:deepseek-chat", temperature=0)


# --------------------------- State ---------------------------
class EmailClassification(TypedDict):
    intent: Literal["question", "bug", "billing", "feature", "complex"]
    urgency: Literal["low", "medium", "high", "critical"]
    topic: str
    summary: str


class EmailAgentState(TypedDict):
    email_content: str
    sender_email: str
    email_id: str
    classification: EmailClassification | None
    search_results: list[str] | None
    customer_history: dict | None
    draft_response: str | None
    messages: list | None


# --------------------------- Nodes ---------------------------
def read_email(state: EmailAgentState) -> dict:
    return {
        "messages": [HumanMessage(content=f"Processing email: {state['email_content']}")]
    }


def classify_intent(
    state: EmailAgentState,
) -> Command[Literal["search_documentation", "human_review", "draft_response", "bug_tracking"]]:
    structured_llm = llm.with_structured_output(EmailClassification)
    # prompt 在 node 内部按需格式化, 不存进 state
    classification_prompt = f"""
    Analyze this customer email and classify it:

    Email: {state['email_content']}
    From: {state['sender_email']}

    Provide classification including intent, urgency, topic, and summary.
    """
    classification = structured_llm.invoke(classification_prompt)

    if classification["intent"] == "billing" or classification["urgency"] == "critical":
        goto = "human_review"
    elif classification["intent"] in ["question", "feature"]:
        goto = "search_documentation"
    elif classification["intent"] == "bug":
        goto = "bug_tracking"
    else:
        goto = "draft_response"

    return Command(update={"classification": classification}, goto=goto)


def search_documentation(state: EmailAgentState) -> Command[Literal["draft_response"]]:
    classification = state.get("classification", {}) or {}
    _query = f"{classification.get('intent', '')} {classification.get('topic', '')}"
    try:
        # 用你的检索逻辑替换这里; 存原始结果而非格式化文本
        search_results = [
            "Reset password via Settings > Security > Change Password",
            "Password must be at least 12 characters",
            "Include uppercase, lowercase, numbers, and symbols",
        ]
    except Exception as e:  # noqa: BLE001 - 可恢复的检索错误也作为结果存下
        search_results = [f"Search temporarily unavailable: {e}"]
    return Command(update={"search_results": search_results}, goto="draft_response")


def bug_tracking(state: EmailAgentState) -> Command[Literal["draft_response"]]:
    ticket_id = "BUG-12345"  # 实际应通过 API 创建
    return Command(
        update={"search_results": [f"Bug ticket {ticket_id} created"]},
        goto="draft_response",
    )


def draft_response(
    state: EmailAgentState,
) -> Command[Literal["human_review", "send_reply"]]:
    classification = state.get("classification", {}) or {}

    context_sections = []
    if state.get("search_results"):
        formatted_docs = "\n".join(f"- {doc}" for doc in state["search_results"])
        context_sections.append(f"Relevant documentation:\n{formatted_docs}")
    if state.get("customer_history"):
        context_sections.append(
            f"Customer tier: {state['customer_history'].get('tier', 'standard')}"
        )

    draft_prompt = f"""
    Draft a response to this customer email:
    {state['email_content']}

    Email intent: {classification.get('intent', 'unknown')}
    Urgency level: {classification.get('urgency', 'medium')}

    {chr(10).join(context_sections)}

    Guidelines:
    - Be professional and helpful
    - Address their specific concern
    - Use the provided documentation when relevant
    """
    response = llm.invoke(draft_prompt)

    needs_review = (
        classification.get("urgency") in ["high", "critical"]
        or classification.get("intent") == "complex"
    )
    goto = "human_review" if needs_review else "send_reply"

    return Command(update={"draft_response": response.content}, goto=goto)


def human_review(state: EmailAgentState) -> Command[Literal["send_reply", END]]:
    classification = state.get("classification", {}) or {}

    # interrupt() 必须放在最前面
    human_decision = interrupt(
        {
            "email_id": state.get("email_id", ""),
            "original_email": state.get("email_content", ""),
            "draft_response": state.get("draft_response", ""),
            "urgency": classification.get("urgency"),
            "intent": classification.get("intent"),
            "action": "Please review and approve/edit this response",
        }
    )

    if human_decision.get("approved"):
        return Command(
            update={
                "draft_response": human_decision.get(
                    "edited_response", state.get("draft_response", "")
                )
            },
            goto="send_reply",
        )
    return Command(update={}, goto=END)


def send_reply(state: EmailAgentState) -> dict:
    print(f"Sending reply: {state['draft_response'][:100]}...")
    return {}


# --------------------------- Graph ---------------------------
workflow = StateGraph(EmailAgentState)
workflow.add_node("read_email", read_email)
workflow.add_node("classify_intent", classify_intent)
workflow.add_node(
    "search_documentation",
    search_documentation,
    retry_policy=RetryPolicy(max_attempts=3),
)
workflow.add_node("bug_tracking", bug_tracking)
workflow.add_node("draft_response", draft_response)
workflow.add_node("human_review", human_review)
workflow.add_node("send_reply", send_reply)

# 因为路由由 node 内的 Command 完成, 这里只需少量必要 edge
workflow.add_edge(START, "read_email")
workflow.add_edge("read_email", "classify_intent")
workflow.add_edge("send_reply", END)

memory = MemorySaver()
app = workflow.compile(checkpointer=memory)


if __name__ == "__main__":
    config = {"configurable": {"thread_id": "customer_123"}}
    initial_state = {
        "email_content": "I was charged twice for my subscription! This is urgent!",
        "sender_email": "customer@example.com",
        "email_id": "email_123",
    }

    app.invoke(initial_state, config)  # 会在 human_review 处暂停
    print("Draft ready for review:",
          (app.get_state(config).values.get("draft_response") or "")[:100])

    human_response = Command(
        resume={"approved": True, "edited_response": "We sincerely apologize..."}
    )
    app.invoke(human_response, config)  # 恢复执行
    print("Email sent successfully!")
