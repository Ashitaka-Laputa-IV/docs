"""Long-term memory: 用 store + Runtime 跨 thread 存取用户级数据。

对应 add-memory.mdx「添加 long-term memory -> 在 node 内部访问 store」。

要点:
- 用 store 编译 graph 后, LangGraph 会自动把 store 注入 node;
  推荐通过 Runtime 访问: runtime.store / runtime.context;
- namespace 常按 (user_id, ...) 划分;
- 换 thread 后只要 user_id 相同, 仍能读到同一份 memory。

为保持可独立运行, 这里不调用 LLM, 只在 node 里读写 store。
"""

import uuid
from dataclasses import dataclass
from typing import TypedDict

from langgraph.graph import START, StateGraph
from langgraph.runtime import Runtime
from langgraph.store.memory import InMemoryStore


class MessagesState(TypedDict):
    messages: list[dict]


@dataclass
class Context:
    user_id: str


def call_model(state: MessagesState, runtime: Runtime[Context]):
    user_id = runtime.context.user_id
    namespace = (user_id, "memories")

    # 检索相关 memory
    memories = runtime.store.search(namespace, limit=3)
    info = " | ".join(d.value["data"] for d in memories) if memories else "(无)"
    print(f"  检索到 memory: {info}")

    # 模拟"用户要求记住"时写入新 memory
    last = state["messages"][-1]["content"]
    if "remember" in last.lower():
        runtime.store.put(
            namespace, str(uuid.uuid4()), {"data": "User name is Bob"}
        )
        print("  已写入新 memory: User name is Bob")

    return {"messages": [{"role": "assistant", "content": f"noted: {last}"}]}


def main() -> None:
    store = InMemoryStore()

    builder = StateGraph(MessagesState, context_schema=Context)
    builder.add_node(call_model)
    builder.add_edge(START, "call_model")
    graph = builder.compile(store=store)

    print("== thread 1: 让 agent 记住名字 ==")
    graph.invoke(
        {"messages": [{"role": "user", "content": "Hi! Remember: my name is Bob"}]},
        {"configurable": {"thread_id": "1"}},
        context=Context(user_id="1"),
    )

    print("\n== thread 2: 新 thread, 相同 user_id, 应能读到 memory ==")
    graph.invoke(
        {"messages": [{"role": "user", "content": "what is my name?"}]},
        {"configurable": {"thread_id": "2"}},
        context=Context(user_id="1"),
    )

    print("\n== thread 3: 新 thread, 不同 user_id, 读不到 memory ==")
    graph.invoke(
        {"messages": [{"role": "user", "content": "what is my name?"}]},
        {"configurable": {"thread_id": "3"}},
        context=Context(user_id="2"),
    )


if __name__ == "__main__":
    main()
