"""fault-tolerance.mdx: 用 set_node_defaults 统一配置 graph 默认值。

一次配置 retry_policy / error_handler / timeout / cache_policy, 避免重复。
- node 级值总覆盖默认值。
- error_handler 与 cache_policy 不作用于 error-handler node。
- 默认值不跨 subgraph 继承。

依赖: pip install langgraph
运行: python set_node_defaults.py
"""

from typing import TypedDict

from langgraph.errors import NodeError
from langgraph.graph import START, StateGraph
from langgraph.types import Command, RetryPolicy, TimeoutPolicy


class State(TypedDict):
    status: str


def fetch_data(state: State) -> State:
    return {"status": "fetched"}


def charge_payment(state: State) -> State:
    raise RuntimeError("payment timeout")


def finalize(state: State) -> State:
    return state


def mark_process_failed(state: State, error: NodeError) -> State:
    # graph 级默认 handler: 把任何未处理失败标记为该流程失败
    return {"status": f"failed at {error.node}: {error.error}"}


def refund_payment(state: State, error: NodeError) -> Command:
    # node 级 handler: 针对 charge_payment 的补偿逻辑
    return Command(
        update={"status": f"compensated after {error.node}"},
        goto="finalize",
    )


graph = (
    StateGraph(State)
    .set_node_defaults(
        retry_policy=RetryPolicy(max_attempts=3),
        error_handler=mark_process_failed,
        timeout=TimeoutPolicy(run_timeout=30),   # 仅对 async node 生效
    )
    .add_node("fetch_data", fetch_data)                       # 用默认 handler
    .add_node("charge_payment", charge_payment,
              error_handler=refund_payment)                   # 覆盖默认 handler
    .add_node("finalize", finalize)
    .add_edge(START, "fetch_data")
    .add_edge("fetch_data", "charge_payment")
    .compile()
)


if __name__ == "__main__":
    # fetch_data 成功; charge_payment 失败后由 refund_payment 补偿并路由到 finalize
    print(graph.invoke({"status": ""}))
