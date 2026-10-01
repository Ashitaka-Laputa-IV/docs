"""event-streaming.mdx: 自定义 stream transformer。

要点:
- required_stream_modes 声明需要底层 graph 发出哪些 Pregel mode (并集),
  未被任何 transformer 请求的 mode 永远不会被发出。
- process() 收到所有已发出事件, 需自行按 event["method"] 过滤。
- StreamChannel(name) 会把每次 push 也作为 custom:<name> 事件送入主事件流;
  StreamChannel() 仅是侧信道投影 (适合不可序列化的进程内句柄)。
- transformer 可在调用时 (transformers=[...]) 或编译时 (compile(transformers=[...])) 注册。

依赖: pip install langgraph
运行: python custom_stream_transformer.py
"""

from typing import TypedDict

from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.stream import ProtocolEvent, StreamChannel, StreamTransformer


class ToolActivity(TypedDict):
    name: str
    status: str


class ToolActivityTransformer(StreamTransformer):
    """具名通道: 投影同时以 custom:tool_activity 事件流入主事件流。"""

    required_stream_modes = ("tools",)

    def __init__(self, scope: tuple[str, ...] = ()) -> None:
        super().__init__(scope)
        self.activity = StreamChannel[ToolActivity]("tool_activity")

    def init(self) -> dict:
        return {"tool_activity": self.activity}

    def process(self, event: ProtocolEvent) -> bool:
        if event["method"] != "tools":
            return True

        data = event["params"]["data"]
        if isinstance(data, dict) and data.get("tool_name") and data.get("event"):
            status = "error" if data["event"] == "tool-error" else "started"
            self.activity.push({"name": data["tool_name"], "status": status})
        return True


class StatsTransformer(StreamTransformer):
    """匿名通道 + finalize(): 统计总 token, 结束前 push 一次。"""

    required_stream_modes = ("messages",)

    def __init__(self, scope: tuple[str, ...] = ()) -> None:
        super().__init__(scope)
        self.total_tokens = 0
        self.total_tokens_log = StreamChannel[int]()

    def init(self) -> dict:
        return {"total_tokens": self.total_tokens_log}

    def process(self, event: ProtocolEvent) -> bool:
        data = event["params"]["data"]
        if isinstance(data, dict):
            usage = data.get("usage") or {}
            self.total_tokens += usage.get("output_tokens") or 0
        return True

    def finalize(self) -> None:
        self.total_tokens_log.push(self.total_tokens)
        self.total_tokens_log.close()


class State(TypedDict):
    text: str


def node(state: State):
    writer = get_stream_writer()
    writer({"kind": "progress", "message": "retrieving context"})
    return {"text": "done"}


graph = (
    StateGraph(State)
    .add_node(node)
    .add_edge(START, "node")
    .add_edge("node", END)
    .compile()
)


if __name__ == "__main__":
    stream = graph.stream_events(
        {"text": ""},
        version="v3",
        transformers=[ToolActivityTransformer, StatsTransformer],
    )

    # 侧信道投影 (匿名/具名都可在 extensions 下访问)
    print("total_tokens:", stream.extensions.get("total_tokens"))
    for item in stream.extensions.get("tool_activity", []):
        print("tool_activity:", item)
