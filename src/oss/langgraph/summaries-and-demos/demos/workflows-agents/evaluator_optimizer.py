"""Evaluator-optimizer (评估器-优化器) —— Graph API 版本。

generator 生成 -> evaluator 评估 -> 不满意则带反馈回环重生成, 直到 Accepted。
依赖: pip install langgraph langchain langchain-deepseek python-dotenv
API key: 自动读取仓库的 src/oss/langgraph/.env (DEEPSEEK_API_KEY / SILICONFLOW_API_KEY / LANGSMITH_API_KEY)
运行: python evaluator_optimizer.py
"""

from dotenv import load_dotenv

load_dotenv()  # 自动向上查找 src/oss/langgraph/.env

from typing import Literal, TypedDict

from langchain.chat_models import init_chat_model
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

llm = init_chat_model("deepseek:deepseek-chat", temperature=0)


class State(TypedDict):
    joke: str
    topic: str
    feedback: str
    funny_or_not: str


class Feedback(BaseModel):
    grade: Literal["funny", "not funny"] = Field(
        description="Decide if the joke is funny or not."
    )
    feedback: str = Field(
        description="If the joke is not funny, provide feedback on how to improve it."
    )


evaluator = llm.with_structured_output(Feedback)


def llm_call_generator(state: State):
    if state.get("feedback"):
        msg = llm.invoke(
            f"Write a joke about {state['topic']} but take into account "
            f"the feedback: {state['feedback']}"
        )
    else:
        msg = llm.invoke(f"Write a joke about {state['topic']}")
    return {"joke": msg.content}


def llm_call_evaluator(state: State):
    grade = evaluator.invoke(f"Grade the joke {state['joke']}")
    return {"funny_or_not": grade.grade, "feedback": grade.feedback}


def route_joke(state: State):
    if state["funny_or_not"] == "funny":
        return "Accepted"
    elif state["funny_or_not"] == "not funny":
        return "Rejected + Feedback"
    return "Accepted"


optimizer_builder = StateGraph(State)
optimizer_builder.add_node("llm_call_generator", llm_call_generator)
optimizer_builder.add_node("llm_call_evaluator", llm_call_evaluator)

optimizer_builder.add_edge(START, "llm_call_generator")
optimizer_builder.add_edge("llm_call_generator", "llm_call_evaluator")
optimizer_builder.add_conditional_edges(
    "llm_call_evaluator",
    route_joke,
    {
        "Accepted": END,
        "Rejected + Feedback": "llm_call_generator",
    },
)

# 注意: 这是无上限循环, 生产环境应加最大迭代次数 (设置 recursion_limit)。
optimizer_workflow = optimizer_builder.compile()


if __name__ == "__main__":
    state = optimizer_workflow.invoke({"topic": "Cats"}, {"recursion_limit": 25})
    print(state["joke"])
