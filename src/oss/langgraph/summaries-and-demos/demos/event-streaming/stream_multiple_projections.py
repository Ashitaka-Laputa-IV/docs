"""event-streaming.mdx: 并发消费多个投影。

- async: astream_events + asyncio.gather
- sync : stream.interleave(...) 按严格到达顺序混合多个投影

投影之间互不消耗对方的事件。

依赖: pip install langgraph langchain langchain-deepseek python-dotenv
API key: 自动读取仓库根目录的 .env (DEEPSEEK_API_KEY / SILICONFLOW_API_KEY / LANGSMITH_API_KEY)
运行: python stream_multiple_projections.py
"""

from dotenv import load_dotenv

load_dotenv()  # 自动向上查找仓库根目录的 .env

import asyncio
from typing import TypedDict

from langchain.chat_models import init_chat_model
from langgraph.graph import END, START, StateGraph

model = init_chat_model("deepseek:deepseek-chat")


class State(TypedDict):
    messages: list


def call_model(state: State):
    return {"messages": state["messages"] + [model.invoke(state["messages"])]}


def subgraph_node(state: State):
    return state


builder = StateGraph(State)
builder.add_node("call_model", call_model)
builder.add_node("sub", subgraph_node)
builder.add_edge(START, "call_model")
builder.add_edge("call_model", "sub")
builder.add_edge("sub", END)
graph = builder.compile()

INPUT = {"messages": [{"role": "user", "content": "Say hi in five words."}]}


async def demo_async() -> None:
    print("=== async: asyncio.gather ===")
    stream = await graph.astream_events(INPUT, version="v3")

    async def consume_messages():
        async for message in stream.messages:
            print(f"[llm] node={message.node}")

    async def consume_subgraphs():
        async for subgraph in stream.subgraphs:
            print(f"[subgraph] path={subgraph.path}")

    await asyncio.gather(consume_messages(), consume_subgraphs())


def demo_interleave() -> None:
    print("\n=== sync: stream.interleave ===")
    stream = graph.stream_events(INPUT, version="v3")
    for name, item in stream.interleave("values", "messages"):
        if name == "values":
            print(f"[state] keys={list(item)}")
        elif name == "messages":
            print(f"[llm] node={item.node}")


if __name__ == "__main__":
    demo_interleave()
    asyncio.run(demo_async())
