"""fault-tolerance.mdx: Functional API 中的超时与重试。

@task 与 @entrypoint 支持相同的 timeout= 与 retry_policy=;
行为与 add_node 一致: 超时抛 NodeTimeoutError、缓冲写入被清除、重试策略决定是否重试。

注意: functional API 不支持 error handler (JS 侧 task 用 retry 选项而非 retryPolicy)。

依赖: pip install langgraph
运行: python functional_api_tasks.py
"""

import asyncio

from langgraph.func import entrypoint, task
from langgraph.types import RetryPolicy, TimeoutPolicy

_attempts = {"n": 0}


@task(
    timeout=TimeoutPolicy(idle_timeout=30),
    retry_policy=RetryPolicy(max_attempts=3),
)
async def call_api(url: str) -> str:
    _attempts["n"] += 1
    if _attempts["n"] < 2:
        raise ConnectionError("transient")
    await asyncio.sleep(0.01)
    return f"response from {url}"


@entrypoint(timeout=60)
async def my_workflow(inputs: dict) -> str:
    return await call_api("https://api.example.com/data")


if __name__ == "__main__":
    print(my_workflow.invoke({}))
    print(f"total attempts: {_attempts['n']}")
