"""裁剪消息(trim_messages): 调用 LLM 前按 token 数截断历史, 避免超出 context window。

对应 add-memory.mdx「裁剪消息」。
不需要 API key(只演示 trim_messages 本身; 真实用法见返回的 messages)。
"""

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.messages.utils import count_tokens_approximately, trim_messages


def fake_history():
    """构造一段多轮对话历史。"""
    msgs = []
    for i in range(6):
        msgs.append(HumanMessage(content=f"这是第 {i} 个问题, 内容需要一些 token 才能体现裁剪效果。"))
        msgs.append(AIMessage(content=f"这是第 {i} 个回答, 同样占用一定数量的 token 以便演示。"))
    return msgs


def main() -> None:
    messages = fake_history()
    print("裁剪前消息条数:", len(messages))

    trimmed = trim_messages(
        messages,
        strategy="last",                     # 保留最后的 max_tokens
        token_counter=count_tokens_approximately,
        max_tokens=128,
        start_on="human",                    # 结果以 human 消息开头(满足多数 provider 要求)
        end_on=("human", "tool"),            # 结果以 human/tool 结尾
    )

    print("裁剪后消息条数:", len(trimmed))
    for m in trimmed:
        print(" -", type(m).__name__, "->", m.content[:24])

    # 在真实 node 中这样用:
    #
    # def call_model(state: MessagesState):
    #     messages = trim_messages(
    #         state["messages"],
    #         strategy="last",
    #         token_counter=count_tokens_approximately,
    #         max_tokens=128,
    #         start_on="human",
    #         end_on=("human", "tool"),
    #     )
    #     response = model.invoke(messages)
    #     return {"messages": [response]}
    #
    # 注意: 裁剪只影响发给 LLM 的内容, 完整历史仍保存在 checkpointer 中。


if __name__ == "__main__":
    main()
