"""Short-term memory: 用 checkpointer + thread_id 让 agent 记住多轮对话。

对应 add-memory.mdx「添加 short-term memory」。

依赖: pip install langgraph langchain langchain-deepseek python-dotenv
API key: 自动读取仓库的 src/oss/langgraph/.env (DEEPSEEK_API_KEY / SILICONFLOW_API_KEY / LANGSMITH_API_KEY)
运行: python short_term_memory.py

生产环境请把 InMemorySaver 换成数据库 checkpointer(见文件末尾注释)。
"""

from dotenv import load_dotenv

load_dotenv()  # 自动向上查找 src/oss/langgraph/.env

from langchain.chat_models import init_chat_model
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, MessagesState, StateGraph

model = init_chat_model("deepseek:deepseek-chat")


def call_model(state: MessagesState):
    response = model.invoke(state["messages"])
    return {"messages": response}


def main() -> None:
    checkpointer = InMemorySaver()

    builder = StateGraph(MessagesState)
    builder.add_node(call_model)
    builder.add_edge(START, "call_model")
    graph = builder.compile(checkpointer=checkpointer)

    # 同一个 thread_id 下的连续调用会累积 state
    config = {"configurable": {"thread_id": "1"}}

    graph.invoke({"messages": [{"role": "user", "content": "hi! i am Bob"}]}, config)
    result = graph.invoke(
        {"messages": [{"role": "user", "content": "what's my name?"}]}, config
    )
    print("模型回答:", result["messages"][-1].content)

    # 换一个 thread_id: 拿不到上一个 thread 的对话记忆
    other = {"configurable": {"thread_id": "2"}}
    result2 = graph.invoke(
        {"messages": [{"role": "user", "content": "what's my name?"}]}, other
    )
    print("新 thread 的回答:", result2["messages"][-1].content)


# 生产环境换成数据库 checkpointer:
#
# from langgraph.checkpoint.postgres import PostgresSaver
# DB_URI = "postgresql://postgres:postgres@localhost:5432/postgres?sslmode=disable"
# with PostgresSaver.from_conn_string(DB_URI) as checkpointer:
#     graph = builder.compile(checkpointer=checkpointer)

if __name__ == "__main__":
    main()
