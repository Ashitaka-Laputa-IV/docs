"""调用已部署到 LangSmith Cloud 的 agent (最小可运行示例)。

来源: src/oss/langgraph/deploy.mdx

依赖: pip install langgraph-sdk python-dotenv
API key: LANGSMITH_API_KEY 自动读取仓库的 src/oss/langgraph/.env
运行: 需自行提供已部署实例地址 (不在 .env 中)
    LANGSMITH_DEPLOYMENT_URL=... python stream_deployed_agent.py

说明:
    - client.runs.stream 的第一个参数传 None 表示 threadless run (不关联对话线程)。
    - "agent" 是 assistant / graph 名称, 定义在 langgraph.json 的 graphs 键下。
"""

import os

from dotenv import load_dotenv

load_dotenv()  # 自动向上查找 src/oss/langgraph/.env (提供 LANGSMITH_API_KEY; LANGSMITH_DEPLOYMENT_URL 需自行提供)

from langgraph_sdk import get_sync_client  # 异步场景用 get_client


def main() -> None:
    client = get_sync_client(
        url=os.environ["LANGSMITH_DEPLOYMENT_URL"],
        api_key=os.environ["LANGSMITH_API_KEY"],
    )

    for chunk in client.runs.stream(
        None,     # Threadless run
        "agent",  # agent 名称, 定义在 langgraph.json
        input={
            "messages": [{
                "role": "human",
                "content": "What is LangGraph?",
            }],
        },
        stream_mode="updates",
    ):
        print(f"Receiving new event of type: {chunk.event}...")
        print(chunk.data)
        print("\n\n")


if __name__ == "__main__":
    main()
