"""Store 基本用法: namespace + put + search + Item 字段。

对应 stores.mdx「基本用法」。不需要任何 API key, 也不依赖 LangGraph graph。
"""

import uuid

from langgraph.store.memory import InMemoryStore


def main() -> None:
    store = InMemoryStore()

    # memory 按 tuple 划分 namespace, 长度任意, 不必是用户特定的
    user_id = "1"
    namespace_for_memory = (user_id, "memories")

    # key 是 memory 的唯一标识符, value(dict)才是 memory 本身
    memory_id = str(uuid.uuid4())
    memory = {"food_preference": "I like pizza"}
    store.put(namespace_for_memory, memory_id, memory)

    # 读取: 最多返回 limit 个(默认 10); InMemoryStore 按插入顺序, 最近的在后
    memories = store.search(namespace_for_memory)
    item = memories[-1]
    print("item.dict():", item.dict())

    print("\nItem 属性:")
    print("  value       :", item.value)
    print("  key         :", item.key)
    print("  namespace   :", item.namespace, "(JSON 化后可能变成 list)")
    print("  created_at  :", item.created_at)
    print("  updated_at  :", item.updated_at)

    # 覆盖写: 使用相同 key 会覆盖原值
    store.put(namespace_for_memory, memory_id, {"food_preference": "I love pizza"})
    print("\n覆盖后 value:", store.search(namespace_for_memory)[-1].value)


if __name__ == "__main__":
    main()
