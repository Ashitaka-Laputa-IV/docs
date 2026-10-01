"""Orchestrator-worker (编排器-工人) —— Functional API 版本。

orchestrator 规划 sections -> 并发为每个 section 派 worker -> synthesizer 汇总。
依赖: pip install langgraph langchain langchain-deepseek python-dotenv
API key: 自动读取仓库的 src/oss/langgraph/.env (DEEPSEEK_API_KEY / SILICONFLOW_API_KEY / LANGSMITH_API_KEY)
运行: python orchestrator_worker.py
"""

from dotenv import load_dotenv

load_dotenv()  # 自动向上查找 src/oss/langgraph/.env

from typing import List

from langchain.chat_models import init_chat_model
from langchain.messages import HumanMessage, SystemMessage
from langgraph.func import entrypoint, task
from pydantic import BaseModel, Field

llm = init_chat_model("deepseek:deepseek-chat", temperature=0)


class Section(BaseModel):
    name: str = Field(description="Name for this section of the report.")
    description: str = Field(
        description="Brief overview of the main topics and concepts to be covered in this section."
    )


class Sections(BaseModel):
    sections: List[Section] = Field(description="Sections of the report.")


planner = llm.with_structured_output(Sections)


@task
def orchestrator(topic: str):
    """生成报告计划"""
    report_sections = planner.invoke(
        [
            SystemMessage(content="Generate a plan for the report."),
            HumanMessage(content=f"Here is the report topic: {topic}"),
        ]
    )
    return report_sections.sections


@task
def llm_call(section: Section):
    """worker 撰写一个 section"""
    result = llm.invoke(
        [
            SystemMessage(content="Write a report section."),
            HumanMessage(
                content=f"Here is the section name: {section.name} "
                f"and description: {section.description}"
            ),
        ]
    )
    return result.content


@task
def synthesizer(completed_sections: list[str]):
    """汇总所有 section"""
    return "\n\n---\n\n".join(completed_sections)


@entrypoint()
def orchestrator_worker(topic: str):
    sections = orchestrator(topic).result()
    # 先发起所有 worker future, 再统一取结果 -> 并发执行
    section_futures = [llm_call(section) for section in sections]
    return synthesizer([fut.result() for fut in section_futures]).result()


if __name__ == "__main__":
    report = orchestrator_worker.invoke("Create a report on LLM scaling laws")
    print(report)
