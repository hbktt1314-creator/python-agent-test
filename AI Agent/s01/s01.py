"""
s01_agent_loop.py - The Agent Loop
The entire secret of an AI coding agent in one pattern:
    while stop_reason == "tool_use":
        response = LLM(messages, tools)
        execute tools
        append results
    +----------+      +-------+      +---------+
    |   User   | ---> |  LLM  | ---> |  Tool   |
    |  prompt  |      |       |      | execute |
    +----------+      +---+---+      +----+----+
                          ^               |
                          |   tool_result |
                          +---------------+
                          (loop continues)
This is the core loop: feed tool results back to the model
until the model decides to stop. Production agents layer
policy, hooks, and lifecycle controls on top.
"""
import os
import subprocess
from anthropic import Anthropic
import tempfile
from dotenv import load_dotenv

# 加载当前目录下的 .env 环境变量文件（用于安全读取 API Key）,若当前目录没有会向上层目录查找.env文件
load_dotenv()
# 初始化 Anthropic 客户端，base_url 指向智谱 AI 的 Anthropic 兼容端点
# 注意：这里不再硬编码 API Key，SDK 会自动从环境变量 ANTHROPIC_API_KEY 中读取
client = Anthropic(base_url="https://open.bigmodel.cn/api/anthropic")
# 定义使用的模型名称
MODEL = "glm-4.6v"

# 定义 Agent 的系统提示词（System Prompt）
# 明确告知模型当前的工作目录，限制其使用 bash 解决问题，并要求“多做少说”
SYSTEM = f"You are a coding agent at {os.getcwd()}. Use bash to solve tasks. Act, don't explain."

# 定义允许 Agent 调用的工具列表，这里只开放了一个名为 bash 的工具
TOOLS = [{
    "name": "bash",
    "description": "Run a shell command in Git Bash environment.", # 工具描述，告知模型何时使用
    "input_schema": {
        "type": "object",
        "properties": {"command": {"type": "string"}},# 接收一个名为 command 的字符串参数
        "required": ["command"],                      # 该参数为必填项
    },
}]
def run_bash(command: str) -> str:
    """
    在本地 Windows 环境下安全执行 Git Bash 命令的函数
    """
    # 打印高亮提示，展示 Agent 申请执行的命令，交由人类审查
    print(f"\n\033[35m[重定向提示] Agent 申请执行命令:\033[0m\n\033[33m{command}\033[0m")

    # 引入“人工确认（Human-in-the-loop）”机制，代替脆弱的黑名单拦截
    ans = input("\033[32m是否批准? (y/n): \033[0m").strip().lower()
    if ans != 'y':
        return "Error: Command execution denied by user." # 如果用户拒绝，直接返回错误信息给模型

    # 本地 Git Bash 的绝对路径（请确保该路径在你的电脑上真实存在）
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
        # 【清理现场】无论执行成功还是失败，最后必须删除生成的临时脚本文件
        if os.path.exists(tmp_script):
            os.unlink(tmp_script)
# -- The core pattern: a while loop that calls tools until the model stops --
def agent_loop(messages: list):
    """
        控制 Agent 执行任务的核心循环逻辑
    """
    max_turns = 10 # 【核心优化】限制单次任务中 Agent 连续调用工具的最大次数，防止死循环刷 Token
    turn = 0
    while turn < max_turns:
        turn += 1
        try:
            # 向大模型发起 API 请求
            response = client.messages.create(
                model=MODEL, system=SYSTEM, messages=messages, tools=TOOLS, max_tokens=4000,
            )
        except Exception as e:
            print(f"API 请求失败: {e}")
            return

        # 用于规范化存储当前轮次大模型回复内容的列表
        assistant_content = []

        # 遍历大模型返回的 Content Blocks，将其从 SDK 对象转为普通字典，防止序列化隐患
        for block in response.content:
            if block.type == "text":
                # 如果模型输出了文本对话，记录并实时打印在控制台
                assistant_content.append({"type": "text", "text": block.text})
                print("Model's Answer:" +block.text)  # 实时打印模型说的话
            elif block.type == "tool_use":
                # 如果模型提出了工具调用申请，记录其 ID、名称和输入参数
                assistant_content.append({
                    "type": "tool_use", "id": block.id,
                    "name": block.name, "input": block.input
                })
        # 将规范化后的模型回复（包含思考文本和工具调用请求）追加到对话历史中
        messages.append({"role": "assistant", "content": assistant_content})

        # 如果大模型不再需要调用工具（说明任务完成或它认为已结束），则跳出循环
        if response.stop_reason != "tool_use":
            break

        # 用于存放工具执行结果的列表
        tool_results = []
        # 遍历刚才记录的模型回复，执行其中所有的工具调用
        for block in assistant_content:
            if block["type"] == "tool_use" and block["name"] == "bash":
                # 调用本地的 run_bash 函数执行命令
                output = run_bash(block["input"]["command"])
                # 按照 Anthropic API 的标准格式组装工具执行结果
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block["id"],
                    "content": output
                })

        # 将工具的执行结果作为 user 角色反馈给大模型，供其在下一轮循环中参考
        messages.append({"role": "user", "content": tool_results})
if __name__ == "__main__":
    history = []

    # 外部主循环：用于持续接收用户的键盘输入
    while True:
        try:
            # 在控制台等待用户输入指令
            # 当你启动代码且不输入任何内容时，程序会卡在（停在） query = input(...) 这一行。
            # 因为 input() 函数的作用就是让程序暂停，静静地等待你在键盘上敲击回车。只要你什么都不输入，程序就会永远停在那里，根本执行不到后面调用 agent_loop 的那行代码
            query = input("\033[36ms01 >> \033[0m").strip()
        except (EOFError, KeyboardInterrupt):
            break  # 捕获异常退出（如 Ctrl+C）

        # 如果输入为空，或者输入 q、exit，则正常退出程序
        if query.strip().lower() in ("q", "exit", ""):
            break

        # 将用户的全新输入追加到全局历史记录中
        history.append({"role": "user", "content": query})

        # 启动 Agent 思考与执行的内部循环
        agent_loop(history)

        print()  # 换行
