"""Prompt chaining (提示链) —— Graph API 版本。

每次 LLM 调用处理上一次调用的输出; 用 gate 函数决定是否需要改进。
依赖: pip install langgraph langchain langchain-deepseek python-dotenv
API key: 自动读取仓库的 src/oss/langgraph/.env (DEEPSEEK_API_KEY / SILICONFLOW_API_KEY / LANGSMITH_API_KEY)
运行: python prompt_chaining.py
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
    improved_joke: str
    final_joke: str


def generate_joke(state: State):
    """第一步: 生成初始笑话"""
    msg = llm.invoke(f"Write a short joke about {state['topic']}")
    return {"joke": msg.content}


def check_punchline(state: State):
    """门控函数: 检查笑话是否有笑点(? 或 !)"""
    if "?" in state["joke"] or "!" in state["joke"]:
        return "Pass"
    return "Fail"


def improve_joke(state: State):
    """第二步: 改进笑话"""
    msg = llm.invoke(f"Make this joke funnier by adding wordplay: {state['joke']}")
    return {"improved_joke": msg.content}


def polish_joke(state: State):
    """第三步: 最终润色"""
    msg = llm.invoke(f"Add a surprising twist to this joke: {state['improved_joke']}")
    return {"final_joke": msg.content}


workflow = StateGraph(State)
workflow.add_node("generate_joke", generate_joke)
workflow.add_node("improve_joke", improve_joke)
workflow.add_node("polish_joke", polish_joke)

workflow.add_edge(START, "generate_joke")
workflow.add_conditional_edges(
    "generate_joke", check_punchline, {"Fail": "improve_joke", "Pass": END}
)
workflow.add_edge("improve_joke", "polish_joke")
workflow.add_edge("polish_joke", END)

chain = workflow.compile()


if __name__ == "__main__":
    state = chain.invoke({"topic": "cats"})
    print("Initial joke:\n", state["joke"])
    if "improved_joke" in state:
        print("\n--- --- ---\nImproved joke:\n", state["improved_joke"])
        print("\n--- --- ---\nFinal joke:\n", state["final_joke"])
    else:
        print("\nFinal joke:\n", state["joke"])
