"""streaming.mdx: 用 messages mode 逐 token stream LLM 输出。

要点: 即使 model 用 .invoke() (而非 .stream()), message 事件仍会被发出。

依赖: pip install langgraph langchain langchain-deepseek python-dotenv
API key: 自动读取仓库根目录的 .env (DEEPSEEK_API_KEY / SILICONFLOW_API_KEY / LANGSMITH_API_KEY)
运行: python llm_tokens_messages.py
"""

from dataclasses import dataclass

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langgraph.graph import START, StateGraph

load_dotenv()  # 自动向上查找仓库根目录的 .env

model = init_chat_model("deepseek:deepseek-chat")


@dataclass
class MyState:
    topic: str
    joke: str = ""


def call_model(state: MyState):
    """调用 LLM 生成一个关于 topic 的笑话。"""
    model_response = model.invoke(
        [{"role": "user", "content": f"Generate a joke about {state.topic}"}]
    )
    return {"joke": model_response.content}


graph = (
    StateGraph(MyState)
    .add_node(call_model)
    .add_edge(START, "call_model")
    .compile()
)


if __name__ == "__main__":
    # messages mode 的 data 是 (message_chunk, metadata) 元组
    for chunk in graph.stream(
        {"topic": "ice cream"},
        stream_mode="messages",
        version="v2",
    ):
        if chunk["type"] == "messages":
            message_chunk, metadata = chunk["data"]
            if message_chunk.content:
                print(message_chunk.content, end="|", flush=True)
