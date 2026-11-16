from dataclasses import dataclass, field
# ==========================================
# 状态机定义与核心组件实例化
# ==========================================
@dataclass
class CompactState:
    has_compacted: bool = False
    last_summary: str = ""
    recent_files: list[str] = field(default_factory=list)