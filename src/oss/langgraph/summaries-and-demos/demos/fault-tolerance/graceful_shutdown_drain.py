"""fault-tolerance.mdx: 优雅关闭 (协作式排空)。

创建 RunControl, 以 control= 传给 invoke/stream; 从任意 thread 调用
request_drain() 通知该运行停止。排空只在 superstep 之间生效, 绝不抢占正在运行的工作。

捕获 GraphDrained 后, 用相同 thread_id、invoke(None, config) 恢复。

注意: request_drain() 不会取消正在运行的 asyncio 任务, 也不会终止 thread;
需要硬性上限时配合优雅超时 + 任务取消。

依赖: pip install langgraph
运行: python graceful_shutdown_drain.py
"""

import asyncio
from typing import TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.errors import GraphDrained
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import RunControl, Runtime


class State(TypedDict):
    step: int


async def step_a(state: State, runtime: Runtime) -> State:
    # 若已被请求排空, 提前返回最小结果
    if runtime.drain_requested:
        return {"step": state["step"], "status": "skipped", "reason": runtime.drain_reason}
    await asyncio.sleep(0.01)
    return {"step": state["step"] + 1}


async def step_b(state: State, runtime: Runtime) -> State:
    await asyncio.sleep(0.01)
    return {"step": state["step"] + 1}


builder = StateGraph(State)
builder.add_node("step_a", step_a)
builder.add_node("step_b", step_b)
builder.add_edge(START, "step_a")
builder.add_edge("step_a", "step_b")
builder.add_edge("step_b", END)
graph = builder.compile(checkpointer=MemorySaver())

config = {"configurable": {"thread_id": "t1"}}
control = RunControl()


if __name__ == "__main__":
    # 模拟 signal handler / supervisor 触发排空
    # control.request_drain("sigterm")

    try:
        result = graph.invoke({"step": 0}, config, control=control)
        if control.drain_requested:
            print("run finished naturally while drain requested")
        else:
            print("result:", result)
    except GraphDrained as e:
        print(f"Drained: {e.reason}")
        # 稍后用相同 config 恢复:
        result = graph.invoke(None, config)
        print("resumed:", result)
