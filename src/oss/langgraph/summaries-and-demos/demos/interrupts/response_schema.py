"""interrupt response_schema: 用 Pydantic model 校验 resume 值。

要点:
- 需要 langgraph>=1.2.12。
- schema 会出现在 Interrupt.response_schema 上 (与 value payload 分开)。
- 有类型 schema 时 interrupt() 返回校验后的对象; 无效输入抛 ValidationError。
- 传 JSON Schema 字典时原样暴露但不校验; 省略 schema 则为 None。

运行: python response_schema.py
"""

from typing import Any

from pydantic import BaseModel
from typing_extensions import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, StateGraph
from langgraph.types import Command, interrupt


class Decision(BaseModel):
    approved: bool
    note: str | None = None


class State(TypedDict):
    answer: Any


def node(state: State) -> State:
    # response_schema 描述恢复时预期输入的格式, 客户端可据此渲染带类型的表单
    answer = interrupt({"question": "approve?"}, response_schema=Decision)
    return {"answer": answer}


graph = (
    StateGraph(State)
    .add_node("node", node)
    .add_edge(START, "node")
    .compile(checkpointer=InMemorySaver())
)

config = {"configurable": {"thread_id": "1"}}

result = graph.invoke({"answer": None}, config)
pending = result["__interrupt__"][0]
assert pending.response_schema == Decision.model_json_schema()
print("response_schema:", pending.response_schema)

# resume 值会被校验并转换为 Decision 实例
result = graph.invoke(Command(resume={"approved": True}), config)
assert result["answer"] == Decision(approved=True)
print("answer:", result["answer"])
