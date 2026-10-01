"""总结消息(summarize): 用模型对较早历史做摘要, 用一段 summary 替换它们。

对应 add-memory.mdx「总结消息」。

依赖: pip install langgraph langchain langchain-deepseek python-dotenv
API key: 自动读取仓库的 src/oss/langgraph/.env (DEEPSEEK_API_KEY / SILICONFLOW_API_KEY / LANGSMITH_API_KEY)
运行: python summarize_messages.py

要点:
- 扩展 MessagesState 增加 summary key;
- 已有 summary 时, 把它作为上下文让模型"续写"摘要;
- 生成摘要后删除除最近 2 条外的所有消息;
- 调用模型时若存在 summary, 把它作为 system message 注入。
"""

from dotenv import load_dotenv

load_dotenv()  # 自动向上查找 src/oss/langgraph/.env

from langchain.chat_models import init_chat_model
from langchain.messages import HumanMessage, RemoveMessage, SystemMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph

model = init_chat_model("deepseek:deepseek-chat")


class State(MessagesState):
    summary: str


def call_model(state: State):
    summary = state.get("summary", "")
    messages = state["messages"]
    if summary:
        # 把已有摘要作为 system message 注入
        messages = [SystemMessage(content=f"Summary of conversation earlier: {summary}")] + messages
    response = model.invoke(messages)
    return {"messages": [response]}


def should_continue(state: State):
    # 消息超过 6 条时触发总结, 否则结束
    if len(state["messages"]) > 6:
        return "summarize_conversation"
    return END


def summarize_conversation(state: State):
    summary = state.get("summary", "")
    if summary:
        prompt = (
            f"This is summary of the conversation to date: {summary}\n\n"
            "Extend the summary by taking into account the new messages above:"
        )
    else:
        prompt = "Create a summary of the conversation above:"

    all_messages = state["messages"] + [HumanMessage(content=prompt)]
    response = model.invoke(all_messages)

    # 删除除最近 2 条外的所有消息
    delete_messages = [RemoveMessage(id=m.id) for m in state["messages"][:-2]]
    return {"summary": response.content, "messages": delete_messages}


def main() -> None:
    workflow = StateGraph(State)
    workflow.add_node("conversation", call_model)
    workflow.add_node("summarize_conversation", summarize_conversation)
    workflow.add_edge(START, "conversation")
    workflow.add_conditional_edges("conversation", should_continue)
    workflow.add_edge("summarize_conversation", END)

    app = workflow.compile(checkpointer=InMemorySaver())

    config = {"configurable": {"thread_id": "1"}}
    app.invoke({"messages": [{"role": "user", "content": "hi, my name is bob"}]}, config)
    app.invoke({"messages": [{"role": "user", "content": "write a short poem about cats"}]}, config)
    app.invoke({"messages": [{"role": "user", "content": "now do the same but for dogs"}]}, config)
    final = app.invoke({"messages": [{"role": "user", "content": "what's my name?"}]}, config)

    print("模型回答:", final["messages"][-1].content)
    print("\n当前 summary:", final.get("summary", "(无)"))
    print("\n剩余消息条数:", len(final["messages"]))


if __name__ == "__main__":
    main()
