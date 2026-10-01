"""枚举 / 分页 / 发现 namespace。

对应 stores.mdx「列出 namespace 中的条目」。
不需要 API key。
"""

from langgraph.store.memory import InMemoryStore


def seed(store: InMemoryStore) -> None:
    store.put(("alice", "memories"), "m1", {"text": "I love pizza"})
    store.put(("alice", "memories"), "m2", {"text": "I am a plumber"})
    store.put(("alice", "preferences"), "p1", {"theme": "dark"})
    store.put(("bob", "memories"), "m3", {"text": "I like cats"})


def main() -> None:
    store = InMemoryStore()
    seed(store)

    # 1) 不传 query / filter: 不带 semantic ranking 地枚举 namespace 下的条目
    items = store.search(("alice", "memories"), limit=100)
    print('search(("alice","memories")) ->', [i.key for i in items])

    # namespace_prefix 是"前缀匹配"而非精确匹配
    prefixed = store.search(("alice",), limit=100)
    print('search(("alice",)) 会连带子 namespace ->', [tuple(i.namespace) for i in prefixed])

    # 2) 分页遍历
    page_size = 1
    offset = 0
    pages = []
    while True:
        page = store.search(("alice",), limit=page_size, offset=offset)
        if not page:
            break
        pages.extend(i.key for i in page)
        offset += page_size
    print("分页后收集到的 key:", pages)

    # 3) 发现有哪些 namespace(在列出每个用户 memory 之前先遍历用户)
    namespaces = store.list_namespaces(prefix=("alice",), max_depth=2)
    print("list_namespaces(prefix=('alice',), max_depth=2) ->", namespaces)


if __name__ == "__main__":
    main()
