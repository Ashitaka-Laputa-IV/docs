"""fault-tolerance.mdx: 超时 (TimeoutPolicy)。

- run_timeout : 硬性墙钟上限, 不随活动刷新。
- idle_timeout: 随进度重置; 仅在指定时长内无进度时触发。
- refresh_on="heartbeat": 只认显式 runtime.heartbeat() 的进度。
- 先触发者取消该次尝试; 超时抛 NodeTimeoutError 并清除失败尝试的写入。

注意: node 超时只对 async node 生效, 同步 node + timeout 会在编译时被拒绝。

依赖: pip install langgraph
运行: python timeouts.py
"""

import asyncio
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import RetryPolicy, TimeoutPolicy


class State(TypedDict):
    result: str


async def slow_node(state: State, runtime: Runtime) -> State:
    # 分批处理, 手动心跳重置空闲计时 (refresh_on="heartbeat" 时必需)
    for batch in range(3):
        await asyncio.sleep(0.05)
        runtime.heartbeat()
    return {"result": "done"}


builder = StateGraph(State)
builder.add_node(
    "slow_node",
    slow_node,
    timeout=TimeoutPolicy(idle_timeout=30, run_timeout=120, refresh_on="heartbeat"),
    retry_policy=RetryPolicy(max_attempts=3),  # NodeTimeoutError 默认可重试
)
builder.add_edge(START, "slow_node")
builder.add_edge("slow_node", END)
graph = builder.compile()


if __name__ == "__main__":
    print(graph.invoke({"result": ""}))
    # 其他写法:
    # builder.add_node("call_model", call_model, timeout=60)          # 秒
    # builder.add_node("call_model", call_model, timeout=timedelta(minutes=2))
    # builder.add_node("call_model", call_model,
    #                  timeout=TimeoutPolicy(run_timeout=120, idle_timeout=30))
