"""HITL 恢复循环: 反复 resume, 直到 graph 不再 interrupt。

事件流版本 (教程推荐, 交互式场景):
    stream = graph.stream_events(input, config=config, version="v3")
    for message in stream.messages:          # 逐 token 的 AI 响应
        for token in message.text: ...
    if not stream.interrupted:               # 检查是否暂停
        final_state = stream.output
        break
    payload = stream.interrupts[0].value     # 读取 interrupt payload
    stream_input = Command(resume=get_user_input(payload))

下面用 invoke() 版本演示同样的循环骨架, 无额外依赖。

运行: python hitl_resume_loop.py
"""

from typing import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


class State(TypedDict):
    name: str | None
    city: str | None


def ask_name(state: State):
    name = interrupt("What's your name?")
    return {"name": name}


def ask_city(state: State):
    city = interrupt("What city do you live in?")
    return {"city": city}


builder = StateGraph(State)
builder.add_node("ask_name", ask_name)
builder.add_node("ask_city", ask_city)
builder.add_edge(START, "ask_name")
builder.add_edge("ask_name", "ask_city")
builder.add_edge("ask_city", END)

graph = builder.compile(checkpointer=InMemorySaver())
config = {"configurable": {"thread_id": "hitl-1"}}

# 模拟来自用户的回答 (真实场景由 get_user_input() 提供)
canned_answers = iter(["Alice", "Shanghai"])

stream_input: dict | Command = {"name": None, "city": None}

while True:
    result = graph.invoke(stream_input, config)

    if "__interrupt__" not in result:
        final_state = result
        break

    payload = result["__interrupt__"][0].value
    user_response = next(canned_answers)
    print(f"Q: {payload}  A: {user_response}")
    stream_input = Command(resume=user_response)

print("final:", final_state)  # -> {'name': 'Alice', 'city': 'Shanghai'}
