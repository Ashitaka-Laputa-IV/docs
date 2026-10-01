"""删除消息: 用 RemoveMessage 从 graph state 永久移除消息。

对应 add-memory.mdx「删除消息」。
不需要 API key(用假 node 代替 LLM)。

要点:
- RemoveMessage 只在带 add_messages reducer 的通道上生效(如 MessagesState);
- 移除特定消息: RemoveMessage(id=m.id);
- 移除全部: RemoveMessage(id=REMOVE_ALL_MESSAGES);
- 删除后必须保证消息历史对所用 LLM provider 合法。
"""

from langchain.messages import RemoveMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.graph.message import REMOVE_ALL_MESSAGES


def call_model(state: MessagesState):
    # 真实场景这里是 model.invoke(state["messages"])
    last = state["messages"][-1].content
    return {"messages": [{"role": "assistant", "content": f"(assistant) {last}"}]}


def delete_messages(state: MessagesState):
    """超过 2 条时, 移除最早的两条。"""
    messages = state["messages"]
    if len(messages) > 2:
        return {"messages": [RemoveMessage(id=m.id) for m in messages[:2]]}
    return {}


def delete_all_messages(state: MessagesState):
    """移除全部消息(此处仅作示例, 未接入 graph)。"""
    return {"messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES)]}


def show(tag: str, graph, config) -> None:
    snapshot = graph.get_state(config)
    pairs = [(m.type, m.content) for m in snapshot.values["messages"]]
    print(f"{tag}: {pairs}")


def main() -> None:
    builder = StateGraph(MessagesState)
    builder.add_sequence([call_model, delete_messages])
    builder.add_edge(START, "call_model")

    graph = builder.compile(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "1"}}

    graph.invoke({"messages": [{"role": "user", "content": "hi! I'm bob"}]}, config)
    show("第 1 轮后", graph, config)

    graph.invoke({"messages": [{"role": "user", "content": "what's my name?"}]}, config)
    show("第 2 轮后", graph, config)
    print("\n注意最早两条已被移除, 但第 2 轮仍能答出 Bob —— 因为删除发生在 LLM 调用之后。")


if __name__ == "__main__":
    main()
