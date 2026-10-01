"""Serializer 配置: pickle 回退 与 加密。

对应 checkpointers.mdx「Serializer」。
- 默认 JsonPlusSerializer 底层用 ormsgpack + JSON, 并非支持所有对象类型;
  pickle_fallback=True 可对 msgpack 不支持的对象(如 Pandas DataFrame)回退到 pickle。
- 加密: 把 EncryptedSerializer 传入 saver 的 serde 参数即可加密所有持久化 state。
  下面注释中的加密示例需要额外安装 pycryptodome, 且需设置 LANGGRAPH_AES_KEY。
"""

from typing import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import END, START, StateGraph


class State(TypedDict):
    foo: str


def node_a(state: State):
    return {"foo": "a"}


def main() -> None:
    # --- pickle 回退 ---
    checkpointer = InMemorySaver(serde=JsonPlusSerializer(pickle_fallback=True))

    workflow = StateGraph(State)
    workflow.add_node(node_a)
    workflow.add_edge(START, "node_a")
    workflow.add_edge("node_a", END)

    graph = workflow.compile(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": "1"}}
    graph.invoke({"foo": ""}, config)
    print("使用 pickle_fallback 的 checkpointer, state:", graph.get_state(config).values)

    # --- 加密(需 pycryptodome 与 LANGGRAPH_AES_KEY, 取消注释即可启用)---
    #
    # import sqlite3
    # from langgraph.checkpoint.serde.encrypted import EncryptedSerializer
    # from langgraph.checkpoint.sqlite import SqliteSaver
    #
    # serde = EncryptedSerializer.from_pycryptodome_aes()  # 读取 LANGGRAPH_AES_KEY
    # checkpointer = SqliteSaver(sqlite3.connect("checkpoint.db"), serde=serde)
    #
    # 在 LangSmith 上运行时, 只要存在 LANGGRAPH_AES_KEY, 加密会自动启用。


if __name__ == "__main__":
    main()
