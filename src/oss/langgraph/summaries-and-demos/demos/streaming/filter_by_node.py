"""streaming.mdx: 按 node 过滤 messages mode 的 token。

用 metadata["langgraph_node"] 只消费指定 node 发出的 token。
示例中 write_joke 与 write_poem 从 START 并发执行。

依赖: pip install langgraph langchain langchain-deepseek python-dotenv
API key: 自动读取仓库的 src/oss/langgraph/.env (DEEPSEEK_API_KEY / SILICONFLOW_API_KEY / LANGSMITH_API_KEY)
运行: python filter_by_node.py
"""

from typing import TypedDict

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langgraph.graph import START, StateGraph

load_dotenv()  # 自动向上查找 src/oss/langgraph/.env

model = init_chat_model("deepseek:deepseek-chat", temperature=0)


class State(TypedDict):
    topic: str
    joke: str
    poem: str


def write_joke(state: State):
    response = model.invoke(
        [{"role": "user", "content": f"Write a joke about {state['topic']}"}]
    )
    return {"joke": response.content}


def write_poem(state: State):
    response = model.invoke(
        [{"role": "user", "content": f"Write a short poem about {state['topic']}"}]
    )
    return {"poem": response.content}


graph = (
    StateGraph(State)
    .add_node(write_joke)
    .add_node(write_poem)
    # 并发写笑话与诗
    .add_edge(START, "write_joke")
    .add_edge(START, "write_poem")
    .compile()
)


if __name__ == "__main__":
    for chunk in graph.stream(
        {"topic": "cats"},
        stream_mode="messages",
        version="v2",
    ):
        if chunk["type"] == "messages":
            msg, metadata = chunk["data"]
            # 只消费 write_poem node 发出的 token
            if msg.content and metadata["langgraph_node"] == "write_poem":
                print(msg.content, end="|", flush=True)
