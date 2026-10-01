"""Parallelization (并行化) —— Graph API 版本。

从 START 同时连出三条边, 三个 LLM 并行生成 joke/story/poem,
再由 aggregator 汇总。
依赖: pip install langgraph langchain langchain-deepseek python-dotenv
API key: 自动读取仓库的 src/oss/langgraph/.env (DEEPSEEK_API_KEY / SILICONFLOW_API_KEY / LANGSMITH_API_KEY)
运行: python parallelization.py
"""

from dotenv import load_dotenv

load_dotenv()  # 自动向上查找 src/oss/langgraph/.env

from typing import TypedDict

from langchain.chat_models import init_chat_model
from langgraph.graph import END, START, StateGraph

llm = init_chat_model("deepseek:deepseek-chat", temperature=0)


class State(TypedDict):
    topic: str
    joke: str
    story: str
    poem: str
    combined_output: str


def call_llm_1(state: State):
    msg = llm.invoke(f"Write a joke about {state['topic']}")
    return {"joke": msg.content}


def call_llm_2(state: State):
    msg = llm.invoke(f"Write a story about {state['topic']}")
    return {"story": msg.content}


def call_llm_3(state: State):
    msg = llm.invoke(f"Write a poem about {state['topic']}")
    return {"poem": msg.content}


def aggregator(state: State):
    combined = f"Here's a story, joke, and poem about {state['topic']}!\n\n"
    combined += f"STORY:\n{state['story']}\n\n"
    combined += f"JOKE:\n{state['joke']}\n\n"
    combined += f"POEM:\n{state['poem']}"
    return {"combined_output": combined}


parallel_builder = StateGraph(State)
parallel_builder.add_node("call_llm_1", call_llm_1)
parallel_builder.add_node("call_llm_2", call_llm_2)
parallel_builder.add_node("call_llm_3", call_llm_3)
parallel_builder.add_node("aggregator", aggregator)

# 三个起点边 = 并行
parallel_builder.add_edge(START, "call_llm_1")
parallel_builder.add_edge(START, "call_llm_2")
parallel_builder.add_edge(START, "call_llm_3")
parallel_builder.add_edge("call_llm_1", "aggregator")
parallel_builder.add_edge("call_llm_2", "aggregator")
parallel_builder.add_edge("call_llm_3", "aggregator")
parallel_builder.add_edge("aggregator", END)

parallel_workflow = parallel_builder.compile()


if __name__ == "__main__":
    state = parallel_workflow.invoke({"topic": "cats"})
    print(state["combined_output"])
