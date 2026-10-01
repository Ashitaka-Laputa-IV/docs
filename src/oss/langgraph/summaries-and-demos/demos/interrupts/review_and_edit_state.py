"""审查并编辑 state: 继续之前让人修改 LLM 生成的文本。

运行: python review_and_edit_state.py
"""

from typing import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


class ReviewState(TypedDict):
    generated_text: str


def review_node(state: ReviewState):
    # 暂停, 把当前内容交给审查者
    updated = interrupt(
        {
            "instruction": "Review and edit this content",
            "content": state["generated_text"],
        }
    )
    # 用编辑后的内容更新 state
    return {"generated_text": updated}


builder = StateGraph(ReviewState)
builder.add_node("review", review_node)
builder.add_edge(START, "review")
builder.add_edge("review", END)

graph = builder.compile(checkpointer=InMemorySaver())

config = {"configurable": {"thread_id": "review-42"}}

initial = graph.invoke({"generated_text": "Initial draft"}, config)
print("interrupts:", initial["__interrupt__"])

# 恢复时提供编辑后的内容
final_state = graph.invoke(Command(resume="Improved draft after review"), config)
print("final:", final_state["generated_text"])  # -> Improved draft after review
