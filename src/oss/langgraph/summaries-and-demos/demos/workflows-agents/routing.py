"""Routing (路由) —— Graph API 版本。

先用 LLM 分类输入 (结构化输出), 再用条件边分流到专用 node。
依赖: pip install langgraph langchain langchain-deepseek python-dotenv
API key: 自动读取仓库根目录的 .env (DEEPSEEK_API_KEY / SILICONFLOW_API_KEY / LANGSMITH_API_KEY)
运行: python routing.py
"""

from dotenv import load_dotenv

load_dotenv()  # 自动向上查找仓库根目录的 .env

from typing import Literal, TypedDict

from langchain.chat_models import init_chat_model
from langchain.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

llm = init_chat_model("deepseek:deepseek-chat", temperature=0)


class Route(BaseModel):
    step: Literal["poem", "story", "joke"] = Field(
        None, description="The next step in the routing process"
    )


router = llm.with_structured_output(Route)


class State(TypedDict):
    input: str
    decision: str
    output: str


def llm_call_1(state: State):
    return {"output": llm.invoke(state["input"]).content}


def llm_call_2(state: State):
    return {"output": llm.invoke(state["input"]).content}


def llm_call_3(state: State):
    return {"output": llm.invoke(state["input"]).content}


def llm_call_router(state: State):
    """用结构化输出作为路由逻辑"""
    decision = router.invoke(
        [
            SystemMessage(
                content="Route the input to story, joke, or poem based on the user's request."
            ),
            HumanMessage(content=state["input"]),
        ]
    )
    return {"decision": decision.step}


def route_decision(state: State):
    if state["decision"] == "story":
        return "llm_call_1"
    elif state["decision"] == "joke":
        return "llm_call_2"
    elif state["decision"] == "poem":
        return "llm_call_3"
    # 兜底: 模型返回意外值时避免下游未定义
    return "llm_call_1"


router_builder = StateGraph(State)
router_builder.add_node("llm_call_1", llm_call_1)
router_builder.add_node("llm_call_2", llm_call_2)
router_builder.add_node("llm_call_3", llm_call_3)
router_builder.add_node("llm_call_router", llm_call_router)

router_builder.add_edge(START, "llm_call_router")
router_builder.add_conditional_edges(
    "llm_call_router",
    route_decision,
    {"llm_call_1": "llm_call_1", "llm_call_2": "llm_call_2", "llm_call_3": "llm_call_3"},
)
router_builder.add_edge("llm_call_1", END)
router_builder.add_edge("llm_call_2", END)
router_builder.add_edge("llm_call_3", END)

router_workflow = router_builder.compile()


if __name__ == "__main__":
    state = router_workflow.invoke({"input": "Write me a joke about cats"})
    print(state["output"])
