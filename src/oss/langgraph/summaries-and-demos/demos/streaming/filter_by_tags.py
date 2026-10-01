"""streaming.mdx: 用 tags 过滤 messages mode 的 LLM token。

给不同 LLM 调用打不同 tags, 再按 metadata["tags"] 过滤, 只消费指定调用的 token。

依赖: pip install langgraph langchain langchain-deepseek python-dotenv
API key: 自动读取仓库的 src/oss/langgraph/.env (DEEPSEEK_API_KEY / SILICONFLOW_API_KEY / LANGSMITH_API_KEY)
运行: python filter_by_tags.py
"""

import asyncio
from typing import TypedDict

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langgraph.graph import START, StateGraph

load_dotenv()  # 自动向上查找 src/oss/langgraph/.env

# joke_model 打上 "joke" tag; poem_model 打上 "poem" tag
joke_model = init_chat_model("deepseek:deepseek-chat", tags=["joke"])
poem_model = init_chat_model("deepseek:deepseek-chat", tags=["poem"])


class State(TypedDict):
    topic: str
    joke: str
    poem: str


async def call_model(state: State, config):
    topic = state["topic"]
    print("Writing joke...")
    # 显式传 config: Python < 3.11 的 async 需要它来正确传播 context
    joke_response = await joke_model.ainvoke(
        [{"role": "user", "content": f"Write a joke about {topic}"}],
        config,
    )
    print("\n\nWriting poem...")
    poem_response = await poem_model.ainvoke(
        [{"role": "user", "content": f"Write a short poem about {topic}"}],
        config,
    )
    return {"joke": joke_response.content, "poem": poem_response.content}


graph = (
    StateGraph(State)
    .add_node(call_model)
    .add_edge(START, "call_model")
    .compile()
)


async def main() -> None:
    async for chunk in graph.astream(
        {"topic": "cats"},
        stream_mode="messages",
        version="v2",
    ):
        if chunk["type"] == "messages":
            msg, metadata = chunk["data"]
            # Python: tags 是列表, 精确匹配
            if metadata["tags"] == ["joke"]:
                print(msg.content, end="|", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
