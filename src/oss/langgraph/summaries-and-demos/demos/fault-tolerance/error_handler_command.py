"""fault-tolerance.mdx: error handler + Command 路由 (Saga / 补偿模式)。

error handler 在所有重试耗尽后运行, 接收 NodeError (node + error 两个字段),
可通过 Command 更新 state 并路由到指定 node。

注意: interrupt() 会绕过重试与 error handler。

依赖: pip install langgraph
运行: python error_handler_command.py
"""

from typing import TypedDict

from langgraph.errors import NodeError
from langgraph.graph import START, StateGraph
from langgraph.types import Command, RetryPolicy


class State(TypedDict):
    status: str


def reserve_inventory(state: State) -> State:
    return {"status": "reserved"}


def charge_payment(state: State) -> State:
    raise RuntimeError("payment timeout")


def payment_error_handler(state: State, error: NodeError) -> Command:
    # 补偿: 更新 state 并路由到 finalize
    return Command(
        update={"status": f"compensated_after_{error.node}: {error.error}"},
        goto="finalize",
    )


def finalize(state: State) -> State:
    return state


graph = (
    StateGraph(State)
    .add_node("reserve_inventory", reserve_inventory)
    .add_node(
        "charge_payment",
        charge_payment,
        retry_policy=RetryPolicy(max_attempts=3, retry_on=ConnectionError),
        error_handler=payment_error_handler,
    )
    .add_node("finalize", finalize)
    .add_edge(START, "reserve_inventory")
    .add_edge("reserve_inventory", "charge_payment")
    .compile()
)


if __name__ == "__main__":
    # charge_payment 抛的是 RuntimeError (不在 retry_on 里),
    # 因此立即触发 handler 补偿, 而不是中止 graph
    print(graph.invoke({"status": ""}))
