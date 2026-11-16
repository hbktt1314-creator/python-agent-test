import os
import subprocess
from anthropic import Anthropic
import tempfile
from dotenv import load_dotenv
from pathlib import Path
from todo_manager import TodoManager

# ==========================================
# 1. 基础配置与客户端初始化
# ==========================================
# 自动读取当前目录下的 .env 文件（保护你的 API 密钥不被泄露）,若当前目录没有会向上层目录查找.env文件
load_dotenv()
# 初始化 Anthropic 客户端，base_url 指向智谱 AI 的 Anthropic 兼容端点
# 注意：这里不再硬编码 API Key，SDK 会自动从环境变量 ANTHROPIC_API_KEY 中读取
client = Anthropic(base_url="https://open.bigmodel.cn/api/anthropic")
# 定义使用的模型名称
MODEL = "glm-4.6v"

# 定义 Agent 的“工作沙盒路径”，即当前运行 Python 的目录
WORKDIR = Path.cwd()
# 定义 Agent 的系统提示词（System Prompt）
# 系统提示词：限定 Agent 的身份、工作目录，并下达“多做少说”的最高指令
SYSTEM = f"You are a coding agent at {os.getcwd()}. Use bash to solve tasks. Act, don't explain."
SUBAGENT_SYSTEM = f"You are a coding subagent at {WORKDIR}. Complete the given task, then summarize your findings."

# ==========================================
# 2. 【核心新增】待办事项管理器 (TodoManager)
# ==========================================

# 实例化全局唯一的待办事项管理器
TODO = TodoManager()

# class AgentTemplate:
#     """
#     从 Markdown 文件的 Frontmatter（元数据前缀）中解析 Agent 定义配置。
#     支持从 .claude/agents/*.md 动态加载不同的智能体人格与设定。
#     """
#     def __init__(self, path):
#         self.path = Path(path)
#         self.name = self.path.stem
#         self.config = {}
#         self.system_prompt = ""
#         self._parse()
#
#     def _parse(self):
#         if not self.path.exists():
#             return
#         text = self.path.read_text(encoding='utf-8')
#         # 正则表达式匹配包裹在 --- 之间的 YAML 元数据
#         match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", text, re.DOTALL)
#         if not match:
#             self.system_prompt = text
#             return
#         # 解析键值对配置
#         for line in match.group(1).splitlines():
#             if ":" in line:
#                 k, _, v = line.partition(":")
#                 self.config[k.strip()] = v.strip()
#         self.system_prompt = match.group(2).strip()
#         self.name = self.config.get("name", self.name)

# ==========================================
# 3. 安全防线与底层工具函数
# ==========================================
def safe_path(p: str) -> Path:
    """
        【路径守护神】防止大模型搞破坏。
        比如模型传入 '../../etc/passwd'，这个函数能强制把它拦在工作目录内。
    """
    # 将用户输入的字符串路径与工作目录拼接，并转换为绝对路径（解析掉其中的 .. 或 .）
    path = (WORKDIR / p).resolve()

    # 检查解析后的绝对路径，是否依然处于工作目录之内
    if not path.is_relative_to(WORKDIR):
        # 如果模型试图逃离沙盒，直接抛出异常阻止
        raise ValueError(f"Path escapes workspace: {p}")
    return path


def run_bash(command: str) -> str:
    """
    【工具1】 在本地 Windows 环境下安全执行 Git Bash 命令的函数
    """
    # 打印高亮提示，展示 Agent 申请执行的命令，交由人类审查
    print(f"\n\033[35m[重定向提示] Agent 申请执行命令:\033[0m\n\033[33m{command}\033[0m")

    # 引入“人工确认（Human-in-the-loop）”机制，代替脆弱的黑名单拦截
    ans = input("\033[32m是否批准? (y/n): \033[0m").strip().lower()
    if ans != 'y':
        return "Error: Command execution denied by user." # 如果用户拒绝，直接返回错误信息给模型

    # Windows 环境下 本地 Git Bash 的绝对路径（请确保该路径在你的电脑上真实存在）
    bash_path = r"D:\installer\Git\Git\bin\bash.exe"
    # 将模型生成的命令写入一个临时的 .sh 脚本文件中，让 Bash 直接读取文件执行
    with tempfile.NamedTemporaryFile(suffix=".sh", delete=False, mode="w", encoding="utf-8") as f:
        f.write(command)
        # 将 Windows 路径中的反斜杠 \ 替换为正斜杠 /，防止 Bash 识别错误
        tmp_script = f.name.replace("\\", "/")
    try:
        # 使用 subprocess 启动 Bash 进程执行临时脚本
        # capture_output=True 捕获标准输出和错误，encoding='utf-8' 防止中文乱码，timeout=120 防止命令卡死
        r = subprocess.run([bash_path, tmp_script], capture_output=True, text=True, timeout=120, encoding='utf-8')
        # 将标准输出和标准错误合并，并去除首尾空白字符
        out = (r.stdout + r.stderr).strip()
        # 限制返回给模型的文本截断长度（最大5万字），防止单次返回内容过大撑爆上下文
        return out[:50000] if out else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Timeout (120s)" # 超时处理
    finally:
        # 【清理现场】无论执行成功还是失败，最后必须删除生成的临时脚本文件,保持电脑整洁
        if os.path.exists(tmp_script):
            os.unlink(tmp_script)

def run_read(path: str, limit: int = None) -> str:
    """【工具2】读取文件内容，并支持行数限制（防止大文件刷屏）"""
    try:
        # 经过安全检查后获取真实路径，并读取全部文本
        text = safe_path(path).read_text(encoding='utf-8')
        lines = text.splitlines()
        # 如果模型指定了行数限制，且文件行数超标，则进行截断
        if limit and limit < len(lines):
            lines = lines[:limit] + [f"... (还有{len(lines) - limit} 行内容被省略)"]
        return "\n".join(lines)[:50000]
    except Exception as e:
        return f"Error: {e}"

def run_write(path: str, content: str) -> str:
    """【工具3】向指定路径写入全新的内容（文件不存在会自动创建）"""
    try:
        fp = safe_path(path)
        # 如果该文件的父级文件夹不存在，则自动连同父级一起创建
        fp.parent.mkdir(parents=True, exist_ok=True)
        # 写入内容
        fp.write_text(content, encoding='utf-8')
        return f"Success: Wrote {len(content)} bytes to {path}"
    except Exception as e:
        return f"Error: {e}"

def run_edit(path: str, old_text: str, new_text: str) -> str:
    """【工具4】精准替换文件中的某一段文本"""
    try:
        fp = safe_path(path)
        content = fp.read_text(encoding='utf-8')

        # 如果找不到要替换的原文本，拒绝修改并报错，防止模型胡乱重写文件
        if old_text not in content:
            return f"Error: Text not found in {path}"

        # 进行替换，最后的参数 1 代表“只替换第一次匹配到的地方”，防止误伤其他地方
        fp.write_text(content.replace(old_text, new_text, 1))
        return f"Success: Edited {path}"
    except Exception as e:
        return f"Error: {e}"

# -- Concurrency safety classification --
# Read-only tools can safely run in parallel; mutating tools must be serialized.
# CONCURRENCY_SAFE = {"read_file"}
# CONCURRENCY_UNSAFE = {"write_file", "edit_file"}

# ==========================================
# 4. 工具的分发映射与声明 (给模型看的名片)
# ==========================================

# 优化点：不再使用深奥的 lambda 表达式，改用直观的普通函数代理
# 当模型说要调用 "read_file" 时，程序知道去执行 run_read 函数
def dispatch_tool(tool_name: str, arguments: dict) -> str:
    """根据工具名称，自动将参数解包并分发给对应的函数"""
    if tool_name == "bash":
        return run_bash(arguments["command"])
    elif tool_name == "read_file":
        return run_read(arguments["path"], arguments.get("limit"))
    elif tool_name == "write_file":
        return run_write(arguments["path"], arguments["content"])
    elif tool_name == "edit_file":
        return run_edit(arguments["path"], arguments["old_text"], arguments["new_text"])
    elif tool_name == "todo":
        return TODO.update(arguments["items"])
    else:
        return f"Error: Unknown tool name '{tool_name}'"

# 定义允许 Agent 调用的工具列表
# 严格按照 Anthropic API 规范定义的工具声明列表
# 大模型阅读了下面这个列表后，才会知道自己拥有哪些能力以及如何传递参数。
# 模型根据TOOLS中定义的规则（name、description、input_schema）返回符合TOOLS定义的数据格式
# 模型返回的数据，通过dispatch_tool函数找模型想要执行的工具函数
# 子智能体的工具
CHILD_TOOLS = [
    {
        "name": "bash",
        "description": "Run a shell command in Git Bash environment.",# 工具描述，告知模型如何使用
        "input_schema": {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        },
    },
    {
        "name": "read_file",
        "description": "Read file contents from workspace safely.",# 工具描述，告知模型如何使用
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path to the file"}, # 接收一个名为 path 的字符串参数，以及参数描述
                "limit": {"type": "integer", "description": "Max lines to read"} # 接收一个名为 limit 的字符串参数，以及参数描述
            },
            "required": ["path"] # 必填的参数
        }
    },
    {
        "name": "write_file",
        "description": "Write new content to a file in workspace.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"}
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "edit_file",
        "description": "Replace a specific text block in an existing file with new text.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old_text": {"type": "string", "description": "The exact text to be replaced"},
                "new_text": {"type": "string", "description": "The text to replace with"}
            },
            "required": ["path", "old_text", "new_text"]
        }
    },
    # 【新增声明】：向模型公开 todo 工具，告诉它如何使用结构化清单
    #
    {
        "name": "todo",
        "description": "Update your plan and structured checklist. Use this to set tasks to 'pending', 'in_progress', or 'completed'. Note: Only ONE task can be 'in_progress' at a time.",
        "input_schema": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "description": "The complete list of todo items, each representing a single specific step.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string", "description": "A unique identifier like 'step_1'"},
                            "text": {"type": "string", "description": "Clear description of what needs to be done"},
                            "status": {"type": "string", "enum": ["pending", "in_progress", "completed"]}
                        },
                        "required": ["id", "text", "status"]
                    }
                }
            },
            "required": ["items"]
        }
    }
]
# 主智能体（Parent）继承全部核心能力，并额外拥有“召唤子智能体”的专属特权
PARENT_TOOLS = CHILD_TOOLS + [
    {
        "name": "task",
        "description": "Spawn a subagent with fresh context to solve a narrow subtask. It shares the filesystem but not conversation history.",
        "input_schema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "Detailed instructions for the subagent"},
                "description": {"type": "string", "description": "Short mnemonic description of the subtask"}
            },
            "required": ["prompt"]
        }
    },
]
# ==========================================
# 5. 核心逻辑：消息管道清洗与 Agent 引擎循环
# ==========================================
def normalize_messages(messages: list) -> list:
    """
    【数据洗涤助手】
    因为大模型在调用工具的过程中，历史记录会变得非常复杂。
    这个函数负责在发送请求给 API 之前，把数据格式清洗成 API 能够百分之百听懂的规范格式。
    """
    cleaned = []
    # 步骤 1: 剔除我们自己定义的内部测试字段（剔除所有以 _ 开头的私有属性）
    for msg in messages:
        clean = {"role": msg["role"]}
        if isinstance(msg.get("content"), str):
            clean["content"] = msg["content"]
        elif isinstance(msg.get("content"), list):
            clean["content"] = [
                {k: v for k, v in block.items() if not k.startswith("_")}
                for block in msg["content"] if isinstance(block, dict)
            ]
        else:
            clean["content"] = msg.get("content", "")
        cleaned.append(clean)
    # 步骤 2: 建立一个全网集合，收集所有目前已经拿到执行结果的 tool_use_id
    existing_results = set()
    for msg in cleaned:
        if isinstance(msg.get("content"), list):
            for block in msg["content"]:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    existing_results.add(block.get("tool_use_id"))
    # 步骤 3: 兜底机制。如果模型之前提出了某个工具申请，但由于意外没有执行
    # 我们必须在这里强行塞入一个假的返回结果 (cancelled)，否则 API 协议会报错拒绝后续交谈
    for msg in cleaned:
        if msg["role"] != "assistant" or not isinstance(msg.get("content"), list):
            continue
        for block in msg["content"]:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use" and block.get("id") not in existing_results:
                cleaned.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": block["id"],"content": "(cancelled)"}]})
    # 步骤 4: 严格合并。API 要求上下轮对话必须是 user -> assistant -> user 的“严格交替”
    # 如果出现了 user -> user 或者 assistant -> assistant，需要把它们的 content 合并在一起
    if not cleaned:
        return cleaned
    merged = [cleaned[0]]
    for msg in cleaned[1:]:
        if msg["role"] == merged[-1]["role"]:
            prev = merged[-1]
            prev_c = prev["content"] if isinstance(prev["content"], list) else [{"type": "text", "text": str(prev["content"])}]
            curr_c = msg["content"] if isinstance(msg["content"], list) else [{"type": "text", "text": str(msg["content"])}]
            prev["content"] = prev_c + curr_c
        else:
            merged.append(msg)
    return merged


# ==========================================
# 6. 核心多智能体循环引擎 (主任务与子任务)
# ==========================================

def run_subagent(prompt: str) -> str:
    """【子智能体动力舱】开辟全新的清白历史上下文，突击局部具体任务"""
    print(f"\n\033[94m[Subagent] 启动子智能体接收任务...\033[0m")
    sub_messages = [{"role": "user", "content": prompt}]  # 干净的崭新历史

    for _ in range(30):  # 子任务自动化运转的最大轮次安全限制
        # 智谱安全防御：在请求前清洗子任务历史消息
        cleaned_sub_messages = normalize_messages(sub_messages)

        try:
            # 子agent对AI模型的API请求
            response = client.messages.create(
                model=MODEL, system=SUBAGENT_SYSTEM, messages=cleaned_sub_messages,
                tools=CHILD_TOOLS, max_tokens=8000,
            )
        except Exception as e:
            print(f"  [子agent] API 请求失败: {e}")
            return f"Error: 子agent API failure: {e}"

        # 记录子智能体的思考内容
        assistant_content = []
        for block in response.content:
            if block.type == "text":
                if block.text.strip():
                    assistant_content.append({"type": "text", "text": block.text})
                    print(f"  [子agent AI模型 的回复]: {block.text}")
            elif block.type == "tool_use":
                assistant_content.append({
                    "type": "tool_use", "id": block.id,
                    "name": block.name, "input": block.input
                })

        sub_messages.append({"role": "assistant", "content": assistant_content})

        # 如果模型不打算调用工具，说明子任务探索完毕，跳出
        if response.stop_reason != "tool_use":
            break

        # 逐个执行子智能体申请的原子工具
        sub_results = []
        for block in assistant_content:
            if block["type"] == "tool_use":
                t_name = block["name"]
                t_input = block["input"]
                t_id = block["id"]
                # 打印提示，让后台人类看清它正在使用哪个专门的辅助工具
                print(f"\n>> 子agent AI模型正在调度专用工具: [{t_name}]")
                # 传入工具名字和参数字典，拿到运行后的输出字符串
                output = dispatch_tool(t_name, t_input)

                # 按照标准响应格式，将工具产出的结果打包
                sub_results.append({
                    "type": "tool_result",
                    "tool_use_id": t_id,
                    "content": str(output)
                })

        sub_messages.append({"role": "user", "content": sub_results})
    # 子agent对话历史过程将被丢弃，只提炼最终结论字符串返回给主智能体
    final_summary = "".join(b.text for b in response.content if b.type == "text")
    return final_summary.strip() if final_summary else "(no summary provided by subagent)"

# -- The core pattern: a while loop that calls tools until the model stops --
# ==========================================
# 7. 【核心改造】Agent 引擎循环 (引入未更新提醒)
# ==========================================
def agent_loop(messages: list):
    """
    【Agent 主引擎】
    控制模型进行“思考 -> 提取工具调用 -> 运行工具 -> 反馈结果 -> 再次思考”的自动化死循环。
    """
    max_turns = 15 # 【核心优化】限制单次任务中 Agent 连续调用工具的最大次数，防止死循环刷 Token,稍微调大上限，因为模型需要额外调用工具管理清单
    turn = 0
    rounds_since_todo = 0  # 追踪计数器：记录大模型连续多少轮工具调用没有更新 Todo
    while turn < max_turns:
        turn += 1
        try:
            # 向大模型发起 API 请求,主agent向AI模型请求
            response = client.messages.create(
                model=MODEL, system=SYSTEM, messages=normalize_messages(messages), tools=PARENT_TOOLS, max_tokens=8000,
            )
        except Exception as e:
            print(f"主agent API 请求失败: {e}")
            return

        # 创建一个列表，用来存储这一轮模型产出的结构化回复
        assistant_content = []
        called_todo_this_turn = False  # 标记：模型这一轮有没有更新 Todo

        # 遍历大模型返回的 Content Blocks，将其从 SDK 对象转为普通字典，防止序列化隐患
        # 解析模型回复的内容，方便后续了解模型想做什么：说了什么话：text，想做什么事：tool_use
        for block in response.content:
            if block.type == "text":
                # 发现文本：代表模型在对人类说话，我们把它记录下来并实时打印到屏幕上
                assistant_content.append({"type": "text", "text": block.text})
                print(f"\n[主agent AI模型 回复]:{block.text}")  # 实时打印模型说的话
            elif block.type == "tool_use":
                # 发现工具申请：代表模型需要申请查阅或修改本地环境，记录工具 ID、名称和入参
                assistant_content.append({
                    "type": "tool_use", "id": block.id,
                    "name": block.name, "input": block.input
                })
                # 如果模型提出了调用 todo 工具的请求，点亮标记
                if block.name == "todo":
                    called_todo_this_turn = True
        # 将规范化后的模型回复（包含思考文本和工具调用请求）追加到对话历史中
        messages.append({"role": "assistant", "content": assistant_content})

        # 如果大模型不再需要调用工具（说明任务完成或它认为已结束），则跳出循环
        if response.stop_reason != "tool_use":
            break

        # 计算并更新计数器
        if called_todo_this_turn:
            rounds_since_todo = 0  # 只要调用了，计数器立刻归零重置
        else:
            rounds_since_todo += 1  # 没调用，计数器加 1

        # 如果走到这里，说明模型这一轮发起了工具调用，我们需要依次去帮它跑代码
        tool_results = []
        # 遍历刚才记录的模型回复，执行其中所有的工具调用：tool_use
        for block in assistant_content:
            if block["type"] == "tool_use" :
                t_name = block["name"]
                t_input = block["input"]
                t_id = block["id"]
                # 🎯【核心变化融合点】：判断是否调用了新型的 "task"（分派子任务）能力
                if t_name == "task":
                    desc = t_input.get("description", "subtask")
                    prompt = t_input.get("prompt", "")
                    # 高亮控制台提示，表明主 Agent 正在派发子任务
                    print(f"\n\033[95m🚀 [主agent] 正在派发子任务 ({desc}): {prompt[:60]}...\033[0m")

                    # 挂起主智能体，直到子智能体执行完毕并交出最终 summary 报告
                    output = run_subagent(prompt)
                else:
                    # 属于传统的原子工具调用 (bash, read_file, etc.)
                    print(f"\n>> 主agent 正在调度专用工具: [{t_name}]")
                    # 传入工具名字和参数字典，拿到运行后的输出字符串
                    output = dispatch_tool(t_name, t_input)

                    if t_name == "todo" and not output.startswith("Error"):
                        print(f"最新的待办面板快照 \033[34m{output}\033[0m")

                # 截断部分输出打印，保持主屏幕清爽
                print(f"  [工具执行结果摘要]: {str(output)[:180]}...")

                # 按照标准响应格式，将工具产出的结果打包
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": t_id,
                    "content": str(output)
                })
        # 【核心新增】：写回技巧（Write-back trick）
        # 如果模型连续 3 轮以上自顾自地执行 Bash 或改文件，却忘记更新自己的 Todo 进度
        # 我们悄悄在返回给模型的工具结果列表的【第一位】注入一条强制性的温和提醒文本
        if rounds_since_todo >= 3:
            print("\033[31m[系统悄悄提示] 监测到模型长时间未维护进度，已自动注入温和提醒。\033[0m")
            tool_results.insert(0, {
                "type": "text",
                "text": "<reminder>Update your todos. Check your current progress and mark completed tasks.</reminder>",
            })
            # 注入一次后，将计数器重置回 1，防止下一轮立刻再次轰炸，给模型一轮反应时间
            rounds_since_todo = 1
        # 将工具的执行结果作为 user 角色反馈给大模型，它会成为下一轮循环中模型思考的依据
        messages.append({"role": "user", "content": tool_results})

# ==========================================
# 8. 键盘交互入口 (程序启动点)
# ==========================================
if __name__ == "__main__":
    history = [] # 全局唯一的对话历史背包，会陪伴整个生命周期
    print("===== 欢迎进入自建 Coding Agent 终端 =====")
    print("提示: 输入 'q' 或 'exit' 可随时退出程序。\n")

    # 外部主循环：用于持续接收用户的键盘输入
    while True:
        try:
            # 在控制台等待用户输入指令
            # 当你启动代码且不输入任何内容时，程序会卡在（停在） query = input(...) 这一行。
            # 因为 input() 函数的作用就是让程序暂停，静静地等待你在键盘上敲击回车。只要你什么都不输入，程序就会永远停在那里，根本执行不到后面调用 agent_loop 的那行代码
            query = input("\033[36ms04 >> \033[0m").strip()
        except (EOFError, KeyboardInterrupt):
            break  # 捕获 Ctrl+C 或强行关闭等异常，优雅退出

        # 如果输入为空，或者输入 q、exit，则正常退出程序
        if query.strip().lower() in ("q", "exit", ""):
            break

        # 构建这一轮任务的独立消息队列，不要把以前几十轮的 tool_result 塞给新任务
        current_task_messages = []
        for past_msg in history:
            if isinstance(past_msg["content"], str):
                current_task_messages.append(past_msg)
            elif isinstance(past_msg["content"], list):
                # 只把文本提炼出来带走，丢弃掉以前零碎的 tool_use
                text_content = "".join([b["text"] for b in past_msg["content"] if b.get("type") == "text"])
                if text_content:
                    current_task_messages.append({"role": past_msg["role"], "content": text_content})

        # 加入当前新问题
        current_task_messages.append({"role": "user", "content": query})
        # 启动 Agent 思考与执行的内部循环
        agent_loop(current_task_messages)

        # 任务结束后，把这一轮沉淀下来的最终结果同步回全局历史
        history.extend(current_task_messages[len(history):])
        # # 将用户的全新输入追加到全局历史记录中
        # history.append({"role": "user", "content": query})

        print()  # 换行，方便与下一次输入做视觉隔断
