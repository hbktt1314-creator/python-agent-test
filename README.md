# Python Agent 学习项目

这是一个使用 Python 从零搭建本地命令行 Agent 的练习项目，代码参考并学习自 ShareAI 官方教程：

- https://learn.shareai.run/en/s06/

项目按 `s01` 到 `s06` 的阶段逐步实现大模型调用、工具使用、任务规划、多 Agent 协作、技能加载和上下文压缩。这些示例主要用于学习、实践和实验，尚不是完整的生产级通用 Agent 框架。

## 项目内容

| 目录/文件 | 内容 |
| --- | --- |
| `AI Agent/s01/` | 最小 Agent 循环：调用模型、请求执行 Bash 命令、将结果返回模型。 |
| `AI Agent/s02/` | 扩展文件读写工具、工具分发与消息格式整理。 |
| `AI Agent/s03/` | 加入待办清单，帮助模型跟踪长任务进度。 |
| `AI Agent/s04/` | 加入主 Agent / 子 Agent 的任务委派。 |
| `AI Agent/s05/` | 面向数据分析的 Agent：技能注册与按需加载、MySQL 查询、待办管理和子 Agent。 |
| `AI Agent/s05/s06.py` | 在数据分析 Agent 基础上增加工具结果落盘、对话记录、上下文压缩与摘要。 |
| `AI Agent/s05/skills/` | 示例技能文档，包括数据分析、数据质量检查和 SQL 开发规范。 |

## 环境要求

- Python 3.10 或更高版本
- Windows 环境建议安装 Git Bash；当前代码中的 Bash 可执行文件路径是本机 Windows 路径，需要按自己的安装位置修改。
- 运行 Agent 需要可用的 Anthropic Messages API 兼容服务及对应 API Key。不同示例配置了不同的服务地址和模型，请按所选服务的要求确认访问权限。
- 使用 `s05.py` 或 `s06.py` 的数据库功能时，还需要安装并运行 MySQL，并准备可访问的数据库。

## 安装

在仓库根目录打开终端，创建并启用虚拟环境：

```bash
python -m venv .venv
```

Windows PowerShell：

```powershell
.venv\Scripts\Activate.ps1
```

macOS / Linux / Git Bash：

```bash
source .venv/bin/activate
```

安装代码中使用的 Python 包：

```bash
python -m pip install anthropic python-dotenv PyMySQL
```

仓库目前没有可用的统一依赖清单；`AI Agent/s02/requirements.txt` 不是有效的 pip 依赖文件，因此不要用它执行 `pip install -r`。

## 配置 API Key

代码使用 `python-dotenv` 加载 `.env`，Anthropic SDK 默认从 `ANTHROPIC_API_KEY` 环境变量读取 Key。可在仓库根目录创建本地 `.env` 文件：

```dotenv
ANTHROPIC_API_KEY=替换为你自己的服务密钥
```

请确认 `.env` 没有被 Git 跟踪或提交。仓库 `.gitignore` 已忽略 `.env`，但仍应在提交前检查变更和 Git 历史。API Key 必须从你实际使用的模型服务获取；不要把真实密钥贴进代码、README、截图或公开提交中。

## 运行示例

在仓库根目录运行入门阶段示例：

```bash
python "AI Agent/s01/s01.py"
python "AI Agent/s02/s02.py"
python "AI Agent/s03/s03.py"
python "AI Agent/s04/s04.py"
```

数据分析 Agent 需要从 `s05` 目录启动，以便程序找到该目录下的技能文件：

```bash
cd "AI Agent/s05"
python s05.py
```

运行带上下文压缩功能的版本：

```bash
cd "AI Agent/s05"
python s06.py
```

程序启动后，在命令行输入任务；输入 `q`、`exit` 或空行退出。Agent 调用 Bash 或执行 SQL 时，请逐项检查操作内容，并只批准你理解且信任的操作。

## 安全说明

- Agent 能调用本地 Bash，并可读写工作目录中的文件；Bash 命令可能修改或删除数据。人工确认提示不是完整的安全隔离机制，运行时应使用专用测试目录和非特权账户，并仔细审查命令。
- `s05.py` 和 `s06.py` 会连接 MySQL。数据库连接参数目前在源码中配置；请在本地替换为自己的测试配置，不要提交真实数据库密码。建议后续改为从环境变量读取凭据。
- `s06.py` 中 SQL 执行确认逻辑目前被注释，Agent 可能直接执行 SQL，包括写入或修改数据的语句。请只连接可丢弃的测试数据库，并在正式使用前增加可靠的只读限制、权限控制和人工审批。
- `s06.py` 可将对话记录和较大的工具输出写入 `.transcripts/`、`.task_outputs/`。这些文件可能包含用户输入、查询结果或敏感数据，分享或提交前应检查并加入 `.gitignore`。
- 项目使用的 `safe_path` 等代码检查不能替代操作系统权限、容器隔离或安全审计。
- 若真实 API Key 或数据库密码曾经提交到 GitHub，即使后来从当前文件删除，旧提交仍可能保留它。应立即轮换/撤销凭据；公开仓库还需评估是否清理 Git 历史。

## 许可证

本项目包含 Apache License 2.0 许可证，详见 [`LICENSE`](LICENSE)。
