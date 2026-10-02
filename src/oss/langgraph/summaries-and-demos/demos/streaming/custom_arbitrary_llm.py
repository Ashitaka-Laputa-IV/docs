"""streaming.mdx: 用 custom mode 从任意 LLM API stream 数据。

即使该 API 没有实现 LangChain chat model 接口, 也能把它的 token
通过 get_stream_writer() 送进 LangGraph 的 stream。

依赖: pip install langgraph openai python-dotenv
API key: 自动读取仓库根目录的 .env (DEEPSEEK_API_KEY / SILICONFLOW_API_KEY / LANGSMITH_API_KEY)
运行: python custom_arbitrary_llm.py
"""

import json
import operator
import os
from typing import Annotated, TypedDict

from dotenv import load_dotenv
from langgraph.config import get_stream_writer
from langgraph.graph import START, StateGraph
from openai import AsyncOpenAI

load_dotenv()  # 自动向上查找仓库根目录的 .env

openai_client = AsyncOpenAI(
    api_key=os.environ["DEEPSEEK_API_KEY"],
    base_url="https://api.deepseek.com",
)
model_name = "deepseek-chat"


async def stream_tokens(model_name: str, messages: list[dict]):
    """原始 OpenAI SDK 的异步 token 生成器。"""
    response = await openai_client.chat.completions.create(
        messages=messages, model=model_name, stream=True
    )
    role = None
    async for chunk in response:
        delta = chunk.choices[0].delta
        if delta.role is not None:
            role = delta.role
        if delta.content:
            yield {"role": role, "content": delta.content}


async def get_items(place: str) -> str:
    """使用该 tool 列出某个地点可能找到的物品。"""
    writer = get_stream_writer()
    response = ""
    async for msg_chunk in stream_tokens(
        model_name,
        [
            {
                "role": "user",
                "content": (
                    "Can you tell me what kind of items "
                    f"i might find in the following place: '{place}'. "
                    "List at least 3 such items separating them by a comma. "
                    "And include a brief description of each item."
                ),
            }
        ],
    ):
        response += msg_chunk["content"]
        writer(msg_chunk)   # 把任意 LLM 的 token 转发到 LangGraph stream
    return response


class State(TypedDict):
    messages: Annotated[list[dict], operator.add]


async def call_tool(state: State):
    ai_message = state["messages"][-1]
    tool_call = ai_message["tool_calls"][-1]

    function_name = tool_call["function"]["name"]
    if function_name != "get_items":
        raise ValueError(f"Tool {function_name} not supported")

    arguments = json.loads(tool_call["function"]["arguments"])
    function_response = await get_items(**arguments)
    tool_message = {
        "tool_call_id": tool_call["id"],
        "role": "tool",
        "name": function_name,
        "content": function_response,
    }
    return {"messages": [tool_message]}


graph = (
    StateGraph(State)
    .add_node(call_tool)
    .add_edge(START, "call_tool")
    .compile()
)

# 用一个包含 tool call 的 AIMessage 来调用 graph
inputs = {
    "messages": [
        {
            "content": None,
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "1",
                    "function": {"arguments": '{"place":"bedroom"}', "name": "get_items"},
                    "type": "function",
                }
            ],
        }
    ]
}


if __name__ == "__main__":
    import asyncio

    async def main() -> None:
        async for chunk in graph.astream(inputs, stream_mode="custom", version="v2"):
            if chunk["type"] == "custom":
                print(chunk["data"]["content"], end="|", flush=True)

    asyncio.run(main())
