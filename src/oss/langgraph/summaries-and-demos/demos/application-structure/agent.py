"""LangGraph 应用结构示例 —— 最小可部署 agent。

对应教程: src/oss/langgraph/application-structure.mdx

配合同目录下的 langgraph.json 使用, 后者通过
    "graphs": { "my_agent": "./agent.py:agent" }
把它注册为可部署的 graph (变量名必须叫 `agent`)。

部署/本地运行:
    pip install -U langgraph
    langgraph dev            # 或交由 LangSmith Deployment 部署

本示例不含真实 LLM, 用一个确定性节点保证开箱即可编译运行。
"""

from langgraph.graph import StateGraph, MessagesState, START, END


def respond(state: MessagesState):
    """一个确定性节点: 返回固定回复 (可替换为真实 model 调用)。"""
    return {"messages": [{"role": "ai", "content": "hello from my_agent"}]}


builder = StateGraph(MessagesState)
builder.add_node("respond", respond)
builder.add_edge(START, "respond")
builder.add_edge("respond", END)

# 关键: 变量名必须与 langgraph.json 中 `./agent.py:agent` 的变量名一致
agent = builder.compile()


if __name__ == "__main__":
    result = agent.invoke({"messages": [{"role": "user", "content": "hi"}]})
    for message in result["messages"]:
        message.pretty_print()
