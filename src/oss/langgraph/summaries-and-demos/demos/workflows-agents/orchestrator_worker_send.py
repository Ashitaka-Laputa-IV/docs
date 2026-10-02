"""Orchestrator-worker —— Graph API + Send API 版本 (动态创建 worker)。

Send("llm_call", {"section": s}) 会动态启动一个 worker node, 每个 worker 有
自己的 state; 所有 worker 的输出通过带 reducer 的共享 key 汇总。

依赖: pip install langgraph langchain langchain-deepseek python-dotenv
API key: 自动读取仓库根目录的 .env (DEEPSEEK_API_KEY / SILICONFLOW_API_KEY / LANGSMITH_API_KEY)
运行: python orchestrator_worker_send.py
"""

from dotenv import load_dotenv

load_dotenv()  # 自动向上查找仓库根目录的 .env

import operator
from typing import Annotated, TypedDict

from langchain.chat_models import init_chat_model
from langchain.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send
from pydantic import BaseModel, Field

llm = init_chat_model("deepseek:deepseek-chat", temperature=0)


class Section(BaseModel):
    name: str = Field(description="Name for this section of the report.")
    description: str = Field(description="Brief overview ...")


class Sections(BaseModel):
    sections: list[Section] = Field(description="Sections of the report.")


planner = llm.with_structured_output(Sections)


# 主 graph state
class State(TypedDict):
    topic: str
    sections: list[Section]
    completed_sections: Annotated[list, operator.add]  # 所有 worker 并行写这里
    final_report: str


# worker state
class WorkerState(TypedDict):
    section: Section
    completed_sections: Annotated[list, operator.add]


def orchestrator(state: State):
    report_sections = planner.invoke(
        [
            SystemMessage(content="Generate a plan for the report."),
            HumanMessage(content=f"Here is the report topic: {state['topic']}"),
        ]
    )
    return {"sections": report_sections.sections}


def llm_call(state: WorkerState):
    """worker 撰写一个 section"""
    section = llm.invoke(
        [
            SystemMessage(
                content="Write a report section following the provided name and "
                "description. Include no preamble for each section. Use markdown formatting."
            ),
            HumanMessage(
                content=f"Here is the section name: {state['section'].name} "
                f"and description: {state['section'].description}"
            ),
        ]
    )
    return {"completed_sections": [section.content]}


def synthesizer(state: State):
    return {"final_report": "\n\n---\n\n".join(state["completed_sections"])}


def assign_workers(state: State):
    """为 plan 里每个 section 分配一个 worker"""
    return [Send("llm_call", {"section": s}) for s in state["sections"]]


builder = StateGraph(State)
builder.add_node("orchestrator", orchestrator)
builder.add_node("llm_call", llm_call)
builder.add_node("synthesizer", synthesizer)

builder.add_edge(START, "orchestrator")
builder.add_conditional_edges("orchestrator", assign_workers, ["llm_call"])
builder.add_edge("llm_call", "synthesizer")
builder.add_edge("synthesizer", END)

orchestrator_worker = builder.compile()


if __name__ == "__main__":
    state = orchestrator_worker.invoke({"topic": "Create a report on LLM scaling laws"})
    print(state["final_report"])
