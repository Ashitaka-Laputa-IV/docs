"""通过 Python SDK (sync) 调用本地 LangGraph Agent Server。

来源: src/oss/langgraph/local-server.mdx

前置:
    1. pip install "langgraph-cli[inmem]" langgraph-sdk
    2. 在应用目录执行 langgraph dev (默认监听 http://localhost:2024)

运行:
    python stream_local_agent_sync.py

说明:
    第一个参数传 None 表示 threadless run; "agent" 是 langgraph.json 中定义的 assistant 名。
"""

from langgraph_sdk import get_sync_client


def main() -> None:
    client = get_sync_client(url="http://localhost:2024")

    for chunk in client.runs.stream(
        None,     # Threadless run
        "agent",  # assistant 名称, 定义在 langgraph.json
        input={
            "messages": [{
                "role": "human",
                "content": "What is LangGraph?",
            }],
        },
        stream_mode="messages-tuple",
    ):
        print(f"Receiving new event of type: {chunk.event}...")
        print(chunk.data)
        print("\n\n")


if __name__ == "__main__":
    main()
