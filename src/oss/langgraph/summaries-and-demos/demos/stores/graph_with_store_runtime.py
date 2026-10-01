"""在 LangGraph 中使用 store: checkpointer + store, 通过 Runtime 读写跨 thread memory。

对应 stores.mdx「在 LangGraph 中使用」。

要点:
- checkpointer 保存 thread 内 state; store 跨 thread 共享数据;
- node 签名里加 Runtime[Context] 即可拿到 runtime.store 与 runtime.context;
- 换一个新 thread, 只要 user_id 相同, 仍能读到同一份 memory。

为保持示例可独立运行, 这里不调用 LLM, 只在 node 中读写 store。
"""

import uuid
from dataclasses import dataclass
from typing import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.store.memory import InMemoryStore


class MessagesState(TypedDict):
    messages: list[dict]


@dataclass
class Context:
    user_id: str


def save_memory(state: MessagesState, runtime: Runtime[Context]):
    """把用户说的话写成一条 long-term memory。"""
    user_id = runtime.context.user_id
    namespace = (user_id, "memories")
    last = state["messages"][-1]["content"]
    runtime.store.put(namespace, str(uuid.uuid4()), {"memory": last})
    return {}


def recall_memory(state: MessagesState, runtime: Runtime[Context]):
    """按最近一条消息检索 memory, 并打印出来。"""
    user_id = runtime.context.user_id
    namespace = (user_id, "memories")
    memories = runtime.store.search(namespace, limit=10)
    info = "\n  ".join(d.value["memory"] for d in memories)
    print(f"[thread={runtime.context.user_id}] 检索到的 memory:\n  {info}")
    return {}


def main() -> None:
    checkpointer = InMemorySaver()
    store = InMemoryStore()

    builder = StateGraph(MessagesState, context_schema=Context)
    builder.add_node("save_memory", save_memory)
    builder.add_node("recall_memory", recall_memory)
    builder.add_edge(START, "save_memory")
    builder.add_edge("save_memory", "recall_memory")
    builder.add_edge("recall_memory", END)

    graph = builder.compile(checkpointer=checkpointer, store=store)

    # thread 1: 写入一条 memory
    print("== thread 1 ==")
    graph.invoke(
        {"messages": [{"role": "user", "content": "I love pizza"}]},
        {"configurable": {"thread_id": "1"}},
        context=Context(user_id="1"),
    )

    # thread 2: 不同 thread, 相同 user_id -> 仍能读到 thread 1 写入的 memory
    print("\n== thread 2(不同 thread, 相同 user_id)==")
    graph.invoke(
        {"messages": [{"role": "user", "content": "hi, tell me about my memories"}]},
        {"configurable": {"thread_id": "2"}},
        context=Context(user_id="1"),
    )

    # thread 3 + 另一个 user_id: 读不到 user 1 的 memory
    print("\n== thread 3(相同 thread 逻辑, 不同 user_id)== 应为空")
    graph.invoke(
        {"messages": [{"role": "user", "content": "hi"}]},
        {"configurable": {"thread_id": "3"}},
        context=Context(user_id="2"),
    )


if __name__ == "__main__":
    main()
