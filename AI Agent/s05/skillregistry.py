import re
from dataclasses import dataclass
from pathlib import Path

@dataclass
class SkillManifest:
    name: str
    description: str
    path: Path

@dataclass
class SkillDocument:
    manifest: SkillManifest
    body: str


# ==========================================
# 动态二级技能库 (Skill Registry)
# ==========================================

class SkillRegistry:
    """
    技能注册中心：实现二级按需加载机制。
    扫描本地 skills/**/*.md 结构，解析 Frontmatter 获取基础元数据。
    """

    def __init__(self, skills_dir: Path):
        self.skills_dir = skills_dir
        self.documents: dict[str, SkillDocument] = {}
        self._load_all()

    def _load_all(self) -> None:
        if not self.skills_dir.exists():
            # 自动创建目录，方便用户首次使用
            self.skills_dir.mkdir(parents=True, exist_ok=True)
            return

        # 递归扫描包含 SKILL.md 的技能包 并解析 name description body 存入 documents
        for path in sorted(self.skills_dir.rglob("SKILL.md")):
            try:
                meta, body = self._parse_frontmatter(path.read_text(encoding='utf-8'))
                name = meta.get("name", path.parent.name)
                description = meta.get("description", "No description")

                manifest = SkillManifest(name=name, description=description, path=path)
                self.documents[name] = SkillDocument(manifest=manifest, body=body.strip())
            except Exception as e:
                print(f"[警告] 解析技能失败 {path}: {e}")

    def _parse_frontmatter(self, text: str) -> tuple[dict, str]:
        # 兼容处理 Windows/Linux 换行符的 Frontmatter 切割
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", text, re.DOTALL)
        if not match:
            return {}, text

        meta = {}
        for line in match.group(1).strip().splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip()
        return meta, match.group(2)

    def describe_available(self) -> str:
        """【第一层】返回极其精简的技能列表，嵌入 System Prompt 降低 Token 消耗"""
        if not self.documents:
            return "  (No specialized skills currently deployed in ./skills/)"
        lines = []
        # 遍历 documents 看看有哪些skill，只获取 skill的name和description
        for name in sorted(self.documents):
            manifest = self.documents[name].manifest
            lines.append(f"- {manifest.name}: {manifest.description}")
        return "\n".join(lines)

    def load_full_text(self, name: str) -> str:
        """【第二层】当大模型需要深度学习该技能时，通过工具按需精准拉取skill全部文本。根据skill的name获取skill的全部信息body"""
        document = self.documents.get(name)
        if not document:
            known = ", ".join(sorted(self.documents)) or "(none)"
            return f"Error: Unknown skill '{name}'. Available skills: {known}"

        # 使用 XML 标签安全包裹，方便大模型精准提取上下文
        return (
            f"<skill name=\"{document.manifest.name}\">\n"
            f"{document.body}\n"
            "</skill>"
        )
