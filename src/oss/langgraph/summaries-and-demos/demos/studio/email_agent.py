"""在 LangSmith Studio 中调试的最小 agent 示例。

来源: src/oss/langgraph/studio.mdx

配套文件: 同目录下的 langgraph.json 会把本文件的 `agent` 暴露给 Agent Server。

依赖: pip install langchain langchain-deepseek langsmith python-dotenv
API key: 自动读取仓库根目录的 .env (DEEPSEEK_API_KEY / SILICONFLOW_API_KEY / LANGSMITH_API_KEY)
运行 (在含 langgraph.json 的项目根目录):
    langgraph dev
    # 然后打开输出中的 Studio URL: https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024
"""

import os

from dotenv import load_dotenv

load_dotenv()  # 自动向上查找仓库根目录的 .env
os.environ.setdefault("LANGSMITH_TRACING", "true")  # .env 未设置时开启追踪

from langchain.agents import create_agent


def send_email(to: str, subject: str, body: str):
    """Send an email"""
    email = {
        "to": to,
        "subject": subject,
        "body": body,
    }
    # ... email sending logic

    return f"Email sent to {to}"


# create_agent 返回一个已编译的 LangGraph graph, 正是 langgraph.json 的 graphs 键期望的值。
agent = create_agent(
    "deepseek:deepseek-chat",
    tools=[send_email],
    system_prompt="You are an email assistant. Always use the send_email tool.",
)


if __name__ == "__main__":
    result = agent.invoke(
        {"messages": [{"role": "user", "content": "Send a test email to alice@example.com"}]}
    )
    print(result["messages"][-1].content)
