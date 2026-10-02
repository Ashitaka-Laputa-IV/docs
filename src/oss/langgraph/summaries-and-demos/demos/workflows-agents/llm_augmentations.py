"""LLM 增强 (workflows-agents "LLM 与增强")。

演示两种基础增强:
- with_structured_output: 让模型返回结构化对象 (Pydantic)
- bind_tools: 让模型返回 tool 调用请求

依赖: pip install langgraph langchain langchain-deepseek python-dotenv
API key: 自动读取仓库根目录的 .env (DEEPSEEK_API_KEY / SILICONFLOW_API_KEY / LANGSMITH_API_KEY)
运行: python llm_augmentations.py
"""

from dotenv import load_dotenv

load_dotenv()  # 自动向上查找仓库根目录的 .env

from langchain.chat_models import init_chat_model
from pydantic import BaseModel, Field

llm = init_chat_model("deepseek:deepseek-chat", temperature=0)


# 结构化输出 schema
class SearchQuery(BaseModel):
    search_query: str | None = Field(
        default=None, description="Query that is optimized web search."
    )
    justification: str | None = Field(
        default=None, description="Why this query is relevant to the user's request."
    )


structured_llm = llm.with_structured_output(SearchQuery)


# 定义一个 tool
def multiply(a: int, b: int) -> int:
    return a * b


llm_with_tools = llm.bind_tools([multiply])


if __name__ == "__main__":
    output = structured_llm.invoke(
        "How does Calcium CT score relate to high cholesterol?"
    )
    print("结构化输出 (SearchQuery 实例):", output)

    msg = llm_with_tools.invoke("What is 2 times 3?")
    print("tool 调用请求:", msg.tool_calls)
