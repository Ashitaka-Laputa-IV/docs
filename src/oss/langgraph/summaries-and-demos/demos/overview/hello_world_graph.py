"""LangGraph 最小 hello world graph (无需任何 LLM)。

对应教程: src/oss/langgraph/overview.mdx

演示 LangGraph 的最小骨架:
    选 state schema -> add_node -> 连 START/END -> compile -> invoke
"""

from langgraph.graph import StateGraph, MessagesState, START, END


def mock_llm(state: MessagesState):
    """模拟一个 LLM 节点: 无论输入是什么, 都返回固定的 AI 消息。"""
    return {"messages": [{"role": "ai", "content": "hello world"}]}


def build_graph():
    graph = StateGraph(MessagesState)
    graph.add_node(mock_llm)
    graph.add_edge(START, "mock_llm")
    graph.add_edge("mock_llm", END)
    return graph.compile()


def main():
    graph = build_graph()
    result = graph.invoke({"messages": [{"role": "user", "content": "hi!"}]})
    for message in result["messages"]:
        message.pretty_print()


if __name__ == "__main__":
    main()
