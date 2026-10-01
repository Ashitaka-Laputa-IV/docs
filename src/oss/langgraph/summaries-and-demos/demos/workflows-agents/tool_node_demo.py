"""ToolNode (prebuilt) 用法示例。

ToolNode 是 prebuilt node, 自动处理 tool 的并行执行、错误处理、state 注入。
注意: 手动调用 ToolNode 时若只传 {"messages": ...} 会丢失自定义 state 字段。
需要一个支持 tool calling 的 llm 时可自行接入; 本 demo 只演示 graph 组装。
"""

from langchain.tools import tool
from langgraph.graph import MessagesState, StateGraph
from langgraph.prebuilt import ToolNode


@tool
def search(query: str) -> str:
    """Search for information."""
    return f"Results for: {query}"


@tool
def calculator(expression: str) -> str:
    """Evaluate a math expression."""
    return str(eval(expression))


builder = StateGraph(MessagesState)
builder.add_node("tools", ToolNode([search, calculator]))
# ... 在此添加其他 node 与 edge (例如 llm_call + should_continue 循环)
graph = builder.compile()


if __name__ == "__main__":
    # 直接给一个带 tool_calls 的消息即可验证 ToolNode 执行 (无需 LLM):
    # 这里仅打印 graph 结构, 实际调用需要接入 llm 产生 tool_calls。
    print("ToolNode graph 已构建:", list(graph.get_graph().nodes.keys()))
