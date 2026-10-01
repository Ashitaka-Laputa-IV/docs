"""streaming.mdx: Python < 3.11 的 async streaming 两种变通写法。

Python < 3.11 的 asyncio task 不支持 context 参数, 因此:
1. 必须把 RunnableConfig 显式传给 ainvoke(), callback 才会传播 (能收到 token)。
2. 不能在 async node/tool 中用 get_stream_writer(), 必须把 writer 作为参数传入。

依赖: pip install langgraph langchain langchain-deepseek python-dotenv
API key: 自动读取仓库的 src/oss/langgraph/.env (DEEPSEEK_API_KEY / SILICONFLOW_API_KEY / LANGSMITH_API_KEY)
运行: python async_writer_and_config.py
"""

import asyncio
from typing import TypedDict

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langgraph.graph import START, StateGraph
from langgraph.types import StreamWriter

load_dotenv()  # 自动向上查找 src/oss/langgraph/.env

model = init_chat_model("deepseek:deepseek-chat")


class State(TypedDict):
    topic: str
    joke: str


# 写法 1: async node 接收 config 并显式传给 ainvoke()
async def call_model(state: State, config):
    topic = state["topic"]
    print("Generating joke...")
    joke_response = await model.ainvoke(
        [{"role": "user", "content": f"Write a joke about {topic}"}],
        config,   # 显式传递, 确保 context 正确传播
    )
    return {"joke": joke_response.content}


# 写法 2: async node 用 writer 参数手动发自定义数据 (替代 get_stream_writer)
async def generate_joke(state: State, writer: StreamWriter):
    writer({"custom_key": "Streaming custom data while generating a joke"})
    return {"joke": f"This is a joke about {state['topic']}"}


messages_graph = (
    StateGraph(State)
    .add_node(call_model)
    .add_edge(START, "call_model")
    .compile()
)

custom_graph = (
    StateGraph(State)
    .add_node(generate_joke)
    .add_edge(START, "generate_joke")
    .compile()
)


async def main() -> None:
    # messages mode: 逐 token 打印
    async for chunk in messages_graph.astream(
        {"topic": "ice cream"}, stream_mode="messages", version="v2"
    ):
        if chunk["type"] == "messages":
            message_chunk, metadata = chunk["data"]
            if message_chunk.content:
                print(message_chunk.content, end="|", flush=True)

    print("\n=== custom mode (writer 参数) ===")
    async for chunk in custom_graph.astream(
        {"topic": "ice cream"}, stream_mode="custom", version="v2"
    ):
        if chunk["type"] == "custom":
            print(chunk["data"])


if __name__ == "__main__":
    asyncio.run(main())
