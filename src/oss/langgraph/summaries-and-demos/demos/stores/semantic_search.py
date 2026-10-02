"""Store 语义搜索: 配置 embedding, 用自然语言 query 检索, 以及 index 参数控制嵌入字段。

对应 stores.mdx「语义搜索」。
依赖: pip install langgraph langchain langchain-openai python-dotenv
API key: 自动读取仓库根目录的 .env (DEEPSEEK_API_KEY / SILICONFLOW_API_KEY / LANGSMITH_API_KEY)
运行: python semantic_search.py
"""

import os

from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from langgraph.store.memory import InMemoryStore

load_dotenv()  # 自动向上查找仓库根目录的 .env

embeddings = OpenAIEmbeddings(
    model="BAAI/bge-m3",
    api_key=os.environ["SILICONFLOW_API_KEY"],
    base_url=os.environ["SILICONFLOW_BASE_URL"],
)


def main() -> None:
    # 配置 embedding model 后, store 才支持语义搜索
    store = InMemoryStore(
        index={
            "embed": embeddings,  # embedding provider
            "dims": 1024,                              # embedding 维度
            "fields": ["food_preference", "$"],        # 要嵌入的字段
        }
    )

    namespace_for_memory = ("1", "memories")

    # index 参数控制哪些字段被嵌入
    store.put(
        namespace_for_memory,
        "1",
        {"food_preference": "I love Italian cuisine", "context": "Discussing dinner plans"},
        index=["food_preference"],  # 只嵌入 food_preference 字段
    )
    # index=False: 仍可检索, 但不可语义搜索
    store.put(
        namespace_for_memory,
        "2",
        {"system_info": "Last updated: 2024-01-01"},
        index=False,
    )

    # 用自然语言 query 找相关 memory, 返回 top 3
    memories = store.search(
        namespace_for_memory,
        query="What does the user like to eat?",
        limit=3,
    )
    for item in memories:
        print("key:", item.key, "| value:", item.value, "| score:", getattr(item, "score", None))


if __name__ == "__main__":
    main()
