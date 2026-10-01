"""带语义搜索的 long-term memory: embedding + query 检索 memories 并喂给模型。

对应 add-memory.mdx「使用语义搜索」。

依赖: pip install langgraph langchain langchain-deepseek langchain-openai python-dotenv
API key: 自动读取仓库的 src/oss/langgraph/.env (DEEPSEEK_API_KEY / SILICONFLOW_API_KEY / LANGSMITH_API_KEY)
运行: python semantic_search_memory.py
"""

import os

from dotenv import load_dotenv

load_dotenv()  # 自动向上查找 src/oss/langgraph/.env

from langchain.chat_models import init_chat_model
from langchain_openai import OpenAIEmbeddings
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.runtime import Runtime
from langgraph.store.memory import InMemoryStore

model = init_chat_model("deepseek:deepseek-chat")

# 创建启用了语义搜索的 store (embedding 使用硅基流动 BAAI/bge-m3, 维度 1024)
embeddings = OpenAIEmbeddings(
    model="BAAI/bge-m3",
    api_key=os.environ["SILICONFLOW_API_KEY"],
    base_url=os.environ["SILICONFLOW_BASE_URL"],
)
store = InMemoryStore(
    index={
        "embed": embeddings,
        "dims": 1024,
    }
)

# 预置两条 memory
store.put(("user_123", "memories"), "1", {"text": "I love pizza"})
store.put(("user_123", "memories"), "2", {"text": "I am a plumber"})


async def chat(state: MessagesState, runtime: Runtime):
    # 按用户最后一条消息做语义检索
    items = await runtime.store.asearch(
        ("user_123", "memories"), query=state["messages"][-1].content, limit=2
    )
    memories = "\n".join(item.value["text"] for item in items)
    memories = f"## Memories of user\n{memories}" if memories else ""
    print("检索到的 memories:\n", memories or "(无)")

    response = await model.ainvoke(
        [
            {"role": "system", "content": f"You are a helpful assistant.\n{memories}"},
            *state["messages"],
        ]
    )
    return {"messages": [response]}


async def main() -> None:
    builder = StateGraph(MessagesState)
    builder.add_node(chat)
    builder.add_edge(START, "chat")
    graph = builder.compile(store=store)

    result = await graph.ainvoke(
        {"messages": [{"role": "user", "content": "I'm hungry"}]}
    )
    print("\n模型回答:", result["messages"][-1].content)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
