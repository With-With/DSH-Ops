"""
元素仓 search-first 匹配服务。

核心思路：
    在 A1/MCP 每生成一个新元素之前，先查询资产仓；
    如果已有高置信匹配，则直接复用，不花 token 重新生成。

匹配优先级（从高到低，短路返回）：
    T1 高置信（high）：同页 + name 精确相等 + role 兼容
    T3 快照匹配（high）：snapshot_hash 完全相等（跨页也可）
    T2 中置信（medium）：name 相等但不同页 / name 包含 + role 相等
    none：全不中，才允许新建

URL 归一化规则：
    - 去除 query string 与 hash
    - 末尾斜杠归一（统一保留一个 /，但根路径保留 /）
    - 端口号保留（与 host 一起保留，不做 host 归一——不同域名视为不同页）
"""
from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urlparse, urlunparse

from .models import Element, PageObject


# ---------------------------------------------------------------------------
# URL 归一化
# ---------------------------------------------------------------------------

def normalize_url_pattern(url: str) -> str:
    """归一化 URL / URL 模式：去 query/hash，末尾斜杠归一，端口保留。

    对完整 URL 与仅含 path 的模式都可用：
    - 完整 URL 保留 scheme + netloc（含端口）+ path
    - 纯 path 只保留 path 部分

    末尾斜杠归一：
    - 空路径或 "/" 保持为 "/"
    - 其余路径统一去掉末尾的 "/"，便于模式匹配
    """
    if not url:
        return ""

    # 处理纯 path（不带 scheme）的情况：补一个假 scheme 以便 urlparse 正确解析
    has_scheme = "://" in url
    parsed = urlparse(url) if has_scheme else urlparse("http://placeholder" + url)

    path = parsed.path or "/"
    # 末尾斜杠归一：非根路径去掉末尾 /
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    if not path:
        path = "/"

    if has_scheme:
        return urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))
    # 纯 path 模式：返回归一化后的 path
    return path


# ---------------------------------------------------------------------------
# PageObject 匹配
# ---------------------------------------------------------------------------

def _pattern_to_regex(url_pattern: str) -> re.Pattern:
    """把 URL 模式（含 {identifier} 占位）转为锚定的正则。

    - {xxx}（任意标识符）匹配一段非斜杠路径段
    - 整串 ^...$ 锚定
    - 归一化在调用方完成
    """
    normalized = normalize_url_pattern(url_pattern)
    # 转义正则特殊字符。注意：re.escape 会把 { 和 } 转义成 \{ 和 \}
    escaped = re.escape(normalized)
    # 把转义后的 \{identifier\} 替换为 [^/]+
    regex_str = re.sub(r"\\\{[a-zA-Z_][a-zA-Z0-9_]*\\\}", r"[^/]+", escaped)
    return re.compile(r"^" + regex_str + r"$")


def match_page(page_url: str) -> Optional[PageObject]:
    """根据 URL 匹配 PageObject。

    匹配策略：
        - 若模式是纯 path（不含 scheme），则只用 URL 的 path 部分匹配
          （同一路径在不同 host/port 视为同一页面，方便多环境部署）
        - 若模式含 scheme+host，则整串匹配（含端口）

    Args:
        page_url: 待匹配的页面 URL（可以是完整 URL 或纯 path）。

    Returns:
        命中的 PageObject 或 None。多个匹配时返回创建最早的那个。
    """
    normalized = normalize_url_pattern(page_url)
    if not normalized:
        return None

    # 解析 normalized 是否为完整 URL
    normalized_has_scheme = "://" in normalized
    normalized_parsed = urlparse(normalized) if normalized_has_scheme else urlparse("http://placeholder" + normalized)
    normalized_path = normalized_parsed.path or "/"

    for page in PageObject.objects.all().order_by("created_at"):
        pattern_has_scheme = "://" in page.url_pattern
        regex = _pattern_to_regex(page.url_pattern)

        if pattern_has_scheme:
            # 模式是完整 URL：整串匹配
            if regex.match(normalized):
                return page
        else:
            # 模式是纯 path：只匹配 path 部分
            if regex.match(normalized_path):
                return page
    return None


# ---------------------------------------------------------------------------
# Element 三级匹配
# ---------------------------------------------------------------------------

def _serialize_element(element: Element) -> dict:
    """把 Element 序列化为 dict（匹配结果用，避免循环依赖 serializer）。"""
    return {
        "id": element.id,
        "page_id": element.page_id,
        "name": element.name,
        "role": element.role,
        "candidates": element.candidates,
        "snapshot_hash": element.snapshot_hash,
        "source": element.source,
        "notes": element.notes,
        "created_at": element.created_at.isoformat() if element.created_at else None,
        "updated_at": element.updated_at.isoformat() if element.updated_at else None,
    }


def _role_matches(a: str, b: str) -> bool:
    """role 兼容判断：双方任一为空即兼容，都非空则必须相等。"""
    if not a or not b:
        return True
    return a.strip().lower() == b.strip().lower()


def match_element(
    page_url: str,
    name: str,
    role: str = "",
    snapshot_hash: Optional[str] = None,
) -> dict:
    """三级匹配元素，返回置信度 + 命中元素 + 候选列表。

    Args:
        page_url: 当前页面 URL（用于判定是否同页）。
        name: 元素名称（通常是可理解的语义名，如 "登录按钮"）。
        role: ARIA 角色，可为空。
        snapshot_hash: 元素快照哈希，可为空。

    Returns:
        dict with keys:
            confidence: "high" | "medium" | "none"
            match: 命中元素的序列化 dict，或 None
            similar: 相似候选列表（仅 medium 时有意义）
            reason: 命中/未命中的原因说明
    """
    name_stripped = (name or "").strip()
    role_stripped = (role or "").strip()

    if not name_stripped:
        return {
            "confidence": "none",
            "match": None,
            "similar": [],
            "reason": "empty name, cannot match",
        }

    page = match_page(page_url)

    # ---- T1: 同页 + name 精确相等 + role 兼容 → high -----------------------
    if page is not None:
        same_page_elements = list(
            Element.objects.filter(page=page, is_deleted=False)
        )
        for el in same_page_elements:
            if el.name.strip() == name_stripped and _role_matches(el.role, role_stripped):
                return {
                    "confidence": "high",
                    "match": _serialize_element(el),
                    "similar": [],
                    "reason": f"T1 exact match on page '{page.name}' by name+role",
                }

    # ---- T3: 快照哈希完全相等（跨页也可） → high ---------------------------
    if snapshot_hash:
        snap_el = (
            Element.objects.filter(snapshot_hash=snapshot_hash, is_deleted=False)
            .order_by("created_at")
            .first()
        )
        if snap_el is not None:
            return {
                "confidence": "high",
                "match": _serialize_element(snap_el),
                "similar": [],
                "reason": "T3 by-snapshot match (cross-page)",
            }

    # ---- T2: 中置信候选 ----------------------------------------------------
    similar: list[Element] = []

    # 子查询 1：name 精确相等但不同页（或页面未命中）
    name_equal = Element.objects.filter(is_deleted=False).exclude(
        id__in=[el.id for el in same_page_elements] if page else []
    )
    # 用 python 过滤 name 精确相等（strip 后）
    name_equal_list = [
        el for el in name_equal if el.name.strip() == name_stripped
    ]
    for el in name_equal_list:
        if _role_matches(el.role, role_stripped):
            similar.append(el)

    # 子查询 2：name 互相包含 + role 相等
    name_contains_list = []
    for el in Element.objects.filter(is_deleted=False).all():
        el_name = el.name.strip()
        if el_name == name_stripped:
            continue  # 已在 name_equal 处理
        if name_stripped in el_name or el_name in name_stripped:
            if _role_matches(el.role, role_stripped) and el not in similar:
                name_contains_list.append(el)

    similar.extend(name_contains_list)

    # 去重并限制数量
    seen = set()
    unique_similar = []
    for el in similar:
        if el.id not in seen:
            seen.add(el.id)
            unique_similar.append(el)
            if len(unique_similar) >= 10:
                break

    if unique_similar:
        return {
            "confidence": "medium",
            "match": None,
            "similar": [_serialize_element(el) for el in unique_similar],
            "reason": (
                "T2 medium: name equality across pages, or name containment "
                "with matching role — needs human review"
            ),
        }

    # ---- none：全不中，该新建了 --------------------------------------------
    return {
        "confidence": "none",
        "match": None,
        "similar": [],
        "reason": "no match found — safe to create new element",
    }
