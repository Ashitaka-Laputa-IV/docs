"""event-streaming.mdx 快速开始: run stream 与类型化投影。

一个 run stream 对象上挂多种投影, 可同时消费:
- stream.messages: chat model 消息 / token 增量
- stream.output  : 等待最终输出

依赖: pip install langgraph langchain langchain-deepseek python-dotenv
API key: 自动读取仓库的 src/oss/langgraph/.env (DEEPSEEK_API_KEY / SILICONFLOW_API_KEY / LANGSMITH_API_KEY)
运行: python quickstart_stream_events.py
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
    response = model.invoke(state["messages"])
    return {"messages": state["messages"] + [response]}


graph = (
    StateGraph(State)
    .add_node(call_model)
    .add_edge(START, "call_model")
    .add_edge("call_model", END)
    .compile()
)


if __name__ == "__main__":
    stream = graph.stream_events(
        {"messages": [{"role": "user", "content": "What is 42 * 17?"}]},
        version="v3",
    )

    # 逐 token 消费 messages 投影
    for message in stream.messages:
        for token in message.text:
            print(token, end="", flush=True)

    # 等待最终输出
    final_state = stream.output
    print("\n\nfinal_state:", final_state)
