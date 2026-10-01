"""客服邮件 agent 的 State 定义 (thinking-in-langgraph Step 3)。

核心原则: state 只存**原始数据**, 不存 prompt 模板 / 格式化文本。
可直接运行, 仅做 schema 定义与示例实例化。
"""

from typing import Literal, TypedDict


class EmailClassification(TypedDict):
    """LLM 结构化输出的分类结果。"""

    intent: Literal["question", "bug", "billing", "feature", "complex"]
    urgency: Literal["low", "medium", "high", "critical"]
    topic: str
    summary: str


class EmailAgentState(TypedDict):
    """所有 node 共享的 memory。"""

    # 原始邮件数据
    email_content: str
    sender_email: str
    email_id: str

    # 分类结果 (单个字典, 直接来自 LLM)
    classification: EmailClassification | None

    # 原始检索 / API 结果
    search_results: list[str] | None  # 原始文档片段列表
    customer_history: dict | None     # 来自 CRM 的原始客户数据

    # 生成内容
    draft_response: str | None
    messages: list[str] | None


if __name__ == "__main__":
    example: EmailAgentState = {
        "email_content": "I was charged twice for my subscription!",
        "sender_email": "customer@example.com",
        "email_id": "email_123",
        "classification": None,
        "search_results": None,
        "customer_history": None,
        "draft_response": None,
        "messages": None,
    }
    print("State 字段:", list(example.keys()))
