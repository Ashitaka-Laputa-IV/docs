"""开启追踪、选择性追踪, 以及为 trace 附加 tags / metadata。

来源: src/oss/langgraph/observability.mdx

依赖: pip install langgraph langchain langchain-deepseek langsmith python-dotenv
API key: 自动读取仓库的 src/oss/langgraph/.env (DEEPSEEK_API_KEY / SILICONFLOW_API_KEY / LANGSMITH_API_KEY)
运行: python tracing_setup.py
"""

import os

from dotenv import load_dotenv

load_dotenv()  # 自动向上查找 src/oss/langgraph/.env
os.environ.setdefault("LANGSMITH_TRACING", "true")  # .env 未设置时开启追踪

from langchain.agents import create_agent
from langsmith import tracing_context


def send_email(to: str, subject: str, body: str) -> str:
    """Send an email"""
    return f"Email sent to {to}"


agent = create_agent(
    "deepseek:deepseek-chat",
    tools=[send_email],
    system_prompt="You are an email assistant. Always use the send_email tool.",
)


def with_tags_and_metadata() -> None:
    """通过 config 为此次调用附加 tags 与 metadata。"""
    agent.invoke(
        {"messages": [{"role": "user", "content": "Send a welcome email"}]},
        config={
            "tags": ["production", "email-assistant", "v1.0"],
            "metadata": {
                "user_id": "user_123",
                "session_id": "session_456",
                "environment": "production",
            },
        },
    )


def selective_tracing() -> None:
    """只追踪 with 块内的调用 (块外是否追踪取决于 LANGSMITH_TRACING)。"""
    # 这段会被追踪, 并写入自定义项目, 附带 tags / metadata
    with tracing_context(
        project_name="email-agent-test",
        enabled=True,
        tags=["production", "email-assistant", "v1.0"],
        metadata={"user_id": "user_123", "session_id": "session_456"},
    ):
        agent.invoke(
            {"messages": [{"role": "user", "content": "Send a test email to alice@example.com"}]}
        )

    # 若未设置 LANGSMITH_TRACING, 这段不会被追踪
    agent.invoke({"messages": [{"role": "user", "content": "Send another email"}]})


if __name__ == "__main__":
    with_tags_and_metadata()
    selective_tracing()
