class TodoManager:
    """
    待办事项管理器：强制大模型保持专注的核心组件。
    约束：同时只能有一个任务处于 'in_progress' 状态。

    任务状态的改变是由大模型在它的“大脑”里决定并主动传过来的，Python 代码只负责“接收和记录”，不负责“主动修改”
    Python 代码变成了基础设施（提供工具和规则），而“什么时候该做什么事”、“任务有没有做完”这些业务决策，全部交给了大模型的智能去判断。
    """

    def __init__(self):
        self.items = []  # 存储结构化的待办事项列表

    def update(self, items: list) -> str:
        validated = []
        in_progress_count = 0

        for item in items:
            # 模型传过来的 item 字典里，已经自带了最新的状态
            # 状态只允许是 pending (等待), in_progress (进行中), completed (已完成)
            # 找不到status，默认给个pending
            status = item.get("status", "pending")
            if status == "in_progress":
                in_progress_count += 1

            validated.append({
                "id": item["id"],
                "text": item["text"],
                "status": status # 这里的 status 已经是模型决定好的新状态了
            })

        # 【硬约束】：如果发现模型同时将两个或更多任务设为“进行中”，直接报错拒绝
        if in_progress_count > 1:
            return "Error: Invalid plan. Only one task can be 'in_progress' at a time."

        self.items = validated
        return self.render()  # 更新成功后，将最新的清单格式化为文本返回给模型
    # 每次大模型更新完它的待办事项后，TodoManager 的 update 函数最后都会调用 self.render()
    # 这个函数会把结构化的字典数据，美化成一段直观的文本（带有 ⏳、🚀、✅ 符号）。
    # 这段渲染出来的文本会作为工具的执行结果直接喂回给大模型
    # 它就会立刻在自己的大脑里建立起深刻的上下文记忆：“哦！第一步我已经彻底做完了，我现在正在做第二步，第三步还没开始。”
    def render(self) -> str:
        """将待办事项清单美化为文本格式，方便大模型和人类阅读"""
        if not self.items:
            return "Your Todo List is currently empty."

        output = ["=== Current Status of Todo List ==="]
        for item in self.items:
            # 根据状态用不同的符号表示
            status_icon = "⏳" if item["status"] == "pending" else "🚀" if item["status"] == "in_progress" else "✅"
            output.append(f"[{item['id']}] {status_icon} {item['text']} ({item['status']})")
        return "\n".join(output)