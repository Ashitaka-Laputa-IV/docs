"""event-streaming.mdx: 迭代原始协议事件 (ProtocolEvent)。

直接迭代 run 对象本身即可拿到原始事件:
  event["seq"]                      # run 内严格递增, 用于排序
  event["method"]                   # 通道名: messages/values/tools/lifecycle/...
  event["params"]["namespace"]      # 从根 graph 到该 scope 的路径 (根为 [])
  event["params"]["timestamp"]      # 墙钟毫秒 (可能漂移, 不用于排序)
  event["params"]["data"]           # 通道相关 payload

依赖: pip install langgraph langchain langchain-deepseek python-dotenv
API key: 自动读取仓库的 src/oss/langgraph/.env (DEEPSEEK_API_KEY / SILICONFLOW_API_KEY / LANGSMITH_API_KEY)
运行: python raw_protocol_events.py
"""

from dotenv import load_dotenv

load_dotenv()  # 自动向上查找 src/oss/langgraph/.env

from typing import TypedDict

from langchain.chat_models import init_chat_model
from langgraph.graph import END, START, StateGraph

model = init_chat_model("deepseek:deepseek-chat")


class State(TypedDict):
    messages: list


def call_model(state: State):
    return {"messages": state["messages"] + [model.invoke(state["messages"])]}


graph = (
    StateGraph(State)
    .add_node(call_model)
    .add_edge(START, "call_model")
    .add_edge("call_model", END)
    .compile()
)


def demo_raw_events() -> None:
    print("=== 原始协议事件 ===")
    stream = graph.stream_events(
        {"messages": [{"role": "user", "content": "What is 42 * 17?"}]},
        version="v3",
    )
    for event in stream:
        namespace = event["params"]["namespace"]
        print(namespace, event["method"], event["params"]["data"])


def demo_content_block_delta() -> None:
    print("\n=== 直接消费 content-block-delta ===")
    stream = graph.stream_events(
        {"messages": [{"role": "user", "content": "What is 42 * 17?"}]},
        version="v3",
    )
    for event in stream:
        if event["method"] != "messages":
            continue
        data = event["params"]["data"][0]
        if not isinstance(data, dict):
            continue
        if data.get("event") != "content-block-delta":
            continue
        block = data.get("delta") or {}
        if block.get("type") == "text-delta":
            print(block.get("text", ""), end="", flush=True)
        elif block.get("type") == "reasoning-delta":
            print(f"[thinking]{block.get('reasoning', '')}", end="", flush=True)


if __name__ == "__main__":
    demo_raw_events()
    demo_content_block_delta()
