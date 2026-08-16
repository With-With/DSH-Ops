"""录制脚本解析器。

移植旧平台 code_parser 思路，纯函数实现，无 Django 依赖。
负责把 Playwright codegen 产物解析为结构化元数据与动作序列：
- 语言识别 / 起始 URL 提取 / 定位器统计 / headless 归一化
- 动作提取器 extract_actions：逐行解析 codegen 脚本动作序列
"""
from __future__ import annotations

import re
from typing import List, Dict, Tuple

# ---------------------------------------------------------------------------
# 基础正则
# ---------------------------------------------------------------------------

URL_RE = re.compile(r'''(?:goto\(|page\.goto\(\s*|goto\s*\(\s*)(["'])(https?://[^"']+)\1''')
PY_LAUNCH_RE = re.compile(r'\.launch\(')
LOCATOR_RE = re.compile(
    r'(?:locator|get_by_role|get_by_text|get_by_label|get_by_placeholder'
    r'|get_by_test_id|get_by_alt_text|get_by_title)\s*\('
)

# goto 单独匹配
_GOTO_RE = re.compile(r'^\s*(?P<page_prefix>page\d*)\.goto\((?P<args>.*)\)\s*$')

# expect_popup 块标记
_POPUP_RE = re.compile(r'^\s*with\s+page\d*\.expect_popup\(\)')

# 从右侧匹配动作调用：.click() / .fill("...") / .press("Enter") 等
# 用贪婪匹配从右往左找到最后一个 .<action>( 作为动作分界线
_ACTION_SUFFIX_RE = re.compile(
    r'\.(?P<action>click|fill|press|check|uncheck|select_option|dblclick)'
    r'\((?P<args>.*)\)\s*$'
)

# 匹配行首的 page / page1 / page2 前缀
_PAGE_PREFIX_RE = re.compile(r'^\s*(?P<page_prefix>page\d*)\.')

# Python 字符串字面量（支持单/双引号与反斜杠转义）
_STR_RE = re.compile(
    r'''(?P<quote>['"])(?P<value>(?:\\.|[^\\'"])*)(?P=quote)'''
)


def _parse_py_string_literal(s: str) -> str:
    """将 Python 字符串字面量（带引号）解析为原始值，处理转义。

    不使用 eval，避免安全风险。支持最常见的 \\n \\t \\\\ \\' \\\" 等。
    """
    s = s.strip()
    if len(s) < 2 or s[0] not in ("'", '"') or s[-1] != s[0]:
        return s
    inner = s[1:-1]
    # 常见转义还原
    out = []
    i = 0
    while i < len(inner):
        if inner[i] == '\\' and i + 1 < len(inner):
            nxt = inner[i + 1]
            mapping = {'n': '\n', 't': '\t', 'r': '\r', '\\': '\\', "'": "'", '"': '"', '0': '\0'}
            out.append(mapping.get(nxt, nxt))
            i += 2
        else:
            out.append(inner[i])
            i += 1
    return ''.join(out)


def _extract_first_string(args_str: str) -> str:
    """从参数字符串里提取第一个字符串字面量的值，提取不到返回空。"""
    m = _STR_RE.search(args_str)
    if m:
        return _parse_py_string_literal(m.group(0))
    return ''


# ---------------------------------------------------------------------------
# 旧平台已有的三大基础能力（移植）
# ---------------------------------------------------------------------------

def detect_language(content: str, filename: str = '') -> str:
    """根据文件名后缀和代码特征判断语言。"""
    name = (filename or '').lower()
    if name.endswith('.py'):
        return 'python'
    if name.endswith('.js') or name.endswith('.ts'):
        return 'javascript'

    stripped = content.lstrip().lower()
    if stripped.startswith('from playwright') or stripped.startswith('import asyncio'):
        return 'python'
    if 'const { chromium' in content or "require('playwright')" in content or "from 'playwright'" in content:
        return 'javascript'
    if 'sync_playwright' in content or 'async_playwright' in content:
        return 'python'
    return 'python'


def extract_start_url(content: str) -> str:
    match = URL_RE.search(content)
    if match:
        return match.group(2)
    return ''


def extract_locators(content: str) -> List[str]:
    """粗粒度提取代码中调用的定位器（用于统计与未来元素库回写）。"""
    return LOCATOR_RE.findall(content)


# ---------------------------------------------------------------------------
# headless 归一化（旧平台思路，简化版：仅替换 headless 参数）
# ---------------------------------------------------------------------------

HEADLESS_ENV_KWARG = 'headless=os.environ.get("HEADLESS", "1") == "1"'


def _find_matching_paren(content: str, open_index: int) -> int:
    depth = 0
    quote = ''
    i = open_index
    while i < len(content):
        ch = content[i]
        if quote:
            if ch == '\\':
                i += 2
                continue
            if ch == quote:
                quote = ''
        elif ch in ('"', "'"):
            quote = ch
        elif ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def _split_top_level_args(args_str: str) -> List[str]:
    args: List[str] = []
    depth = 0
    quote = ''
    cur = ''
    i = 0
    while i < len(args_str):
        ch = args_str[i]
        if quote:
            cur += ch
            if ch == '\\' and i + 1 < len(args_str):
                cur += args_str[i + 1]
                i += 2
                continue
            if ch == quote:
                quote = ''
        elif ch in ('"', "'"):
            quote = ch
            cur += ch
        elif ch in '([{':
            depth += 1
            cur += ch
        elif ch in ')]}':
            depth -= 1
            cur += ch
        elif ch == ',' and depth == 0:
            if cur.strip():
                args.append(cur.strip())
            cur = ''
        else:
            cur += ch
        i += 1
    if cur.strip():
        args.append(cur.strip())
    return args


def _rewrite_launch_headless(content: str) -> str:
    result: List[str] = []
    pos = 0
    for m in PY_LAUNCH_RE.finditer(content):
        open_index = m.end() - 1
        close_index = _find_matching_paren(content, open_index)
        if close_index == -1:
            continue
        args_str = content[open_index + 1:close_index]
        result.append(content[pos:m.start()])
        if 'os.environ.get("HEADLESS"' in args_str or "os.environ.get('HEADLESS'" in args_str:
            result.append(content[m.start():close_index + 1])
        else:
            new_args = []
            replaced = False
            for arg in _split_top_level_args(args_str):
                if re.match(r'headless\s*=', arg):
                    new_args.append(HEADLESS_ENV_KWARG)
                    replaced = True
                else:
                    new_args.append(arg)
            if not replaced:
                new_args.append(HEADLESS_ENV_KWARG)
            result.append('.launch(' + ', '.join(new_args) + ')')
        pos = close_index + 1
    result.append(content[pos:])
    return ''.join(result)


def normalize_code(content: str, language: str = '') -> str:
    language = language or detect_language(content)
    if language == 'python':
        normalized = _rewrite_launch_headless(content)
        if 'import os' not in normalized:
            normalized = 'import os\n' + normalized
        return normalized
    return content


# ---------------------------------------------------------------------------
# 动作提取器（P1 新增）
# ---------------------------------------------------------------------------

# 支持的定位器方法 -> locator_type 映射
LOCATOR_METHOD_MAP = {
    'get_by_role': 'role',
    'get_by_text': 'text',
    'get_by_label': 'label',
    'get_by_placeholder': 'placeholder',
    'get_by_test_id': 'testid',
    'get_by_alt_text': 'alttext',
    'get_by_title': 'title',
    'locator': 'css',
}

# 支持的动作类型
SUPPORTED_ACTIONS = {'goto', 'click', 'fill', 'press', 'check', 'uncheck', 'select_option', 'dblclick'}


def _parse_locator_chain(chain_str: str) -> Tuple[str, str, str]:
    """解析定位器调用链，返回 (locator_type, locator_value, name)。

    支持：
      page.get_by_role("textbox", name="请输入用户名")
      page.get_by_text("版本管理")
      page.locator("#id")
    如果有链式调用（get_by_role().get_by_text()），以最外层为准。
    """
    # 找到第一个方法调用（最外层）
    # 按点分割后找第一个匹配的方法
    parts = chain_str.split('.')
    locator_type = ''
    locator_value = ''
    name = ''

    # 找第一个定位器方法
    for part in parts:
        for method, ltype in LOCATOR_METHOD_MAP.items():
            if part.startswith(method + '('):
                locator_type = ltype
                # 提取参数部分
                args_start = part.index('(')
                args_end = _find_matching_paren(part, args_start)
                if args_end == -1:
                    args_str = part[args_start + 1:]
                else:
                    args_str = part[args_start + 1:args_end]

                # 对于 role/text 等，第一个位置参数是值
                args_list = _split_top_level_args(args_str)
                if args_list:
                    first = args_list[0]
                    locator_value = _extract_first_string(first) or first

                # 提取 name= 参数
                for arg in args_list:
                    arg_stripped = arg.strip()
                    if arg_stripped.startswith('name='):
                        name_part = arg_stripped[len('name='):]
                        name = _extract_first_string(name_part) or name_part.strip()
                    elif arg_stripped.startswith('exact='):
                        # exact 不影响值
                        pass

                return locator_type, locator_value, name

    return locator_type, locator_value, name


def _parse_action_line(stripped: str) -> Tuple[bool, str, str, str]:
    """从行尾向前解析动作调用。

    返回 (matched, action_name, action_args, locator_chain_str)。
    locator_chain_str 是 page 前缀之后、动作之前的部分（定位器调用链）。
    """
    # 必须以 ) 结尾
    if not stripped.endswith(')'):
        return False, '', '', ''

    # 从右向左找匹配的 '(' —— 这是最外层动作的参数列表开始
    depth = 0
    quote = ''
    action_open = -1
    i = len(stripped) - 1
    while i >= 0:
        ch = stripped[i]
        if quote:
            if ch == '\\' and i - 1 >= 0:
                i -= 2
                continue
            if ch == quote:
                quote = ''
        elif ch in ('"', "'"):
            quote = ch
        elif ch == ')':
            depth += 1
        elif ch == '(':
            depth -= 1
            if depth == 0:
                action_open = i
                break
        i -= 1

    if action_open == -1:
        return False, '', '', ''

    # action_open 是最外层 '(' 的位置，向左找 '.' 得到动作名
    dot_pos = stripped.rfind('.', 0, action_open)
    if dot_pos == -1:
        return False, '', '', ''

    action_name = stripped[dot_pos + 1:action_open]
    action_args = stripped[action_open + 1:-1]  # 去掉外层括号

    # dot_pos 左边是定位器调用链，再往左找 page. / page\d. 前缀
    pm = _PAGE_PREFIX_RE.match(stripped)
    if not pm:
        return False, '', '', ''
    page_prefix_end = pm.end()  # page. 之后的位置
    locator_chain = stripped[page_prefix_end:dot_pos]

    # 验证动作名
    if action_name not in SUPPORTED_ACTIONS:
        return False, action_name, action_args, locator_chain

    return True, action_name, action_args, locator_chain


def extract_actions(content: str) -> Tuple[List[Dict], List[str]]:
    """逐行解析 codegen 脚本动作序列。

    返回 (actions, warnings)。
    每个动作 dict: {index, type, locator_type, locator_value, name, value, raw}
    """
    actions: List[Dict] = []
    warnings: List[str] = []
    lines = content.splitlines()

    index = 0
    for lineno, line in enumerate(lines, 1):
        stripped = line.strip()
        # 跳过空行与纯注释
        if not stripped or stripped.startswith('#'):
            continue
        # 跳过 def/import/with/context.close/browser.close 等非动作行
        if (stripped.startswith('def ') or stripped.startswith('import ')
                or stripped.startswith('from ') or stripped.startswith('browser =')
                or stripped.startswith('context =') or stripped.startswith('page =')
                or (stripped.startswith('context.') and stripped.endswith('close()'))
                or (stripped.startswith('browser.') and stripped.endswith('close()'))
                or stripped.startswith('with sync_playwright')
                or stripped == 'with sync_playwright() as playwright:'):
            continue

        # expect_popup 块 -> 记 popup 标记
        if _POPUP_RE.match(line):
            actions.append({
                'index': index,
                'type': 'popup',
                'locator_type': '',
                'locator_value': '',
                'name': '',
                'value': '',
                'raw': stripped,
            })
            index += 1
            continue

        # goto
        m = _GOTO_RE.match(line)
        if m:
            args_str = m.group('args')
            url = _extract_first_string(args_str)
            actions.append({
                'index': index,
                'type': 'goto',
                'locator_type': '',
                'locator_value': '',
                'name': '',
                'value': url,
                'raw': stripped,
            })
            index += 1
            continue

        # 通用动作：从右向左解析
        matched, action_name, action_args, locator_chain = _parse_action_line(stripped)
        if matched:
            locator_type, locator_value, name = _parse_locator_chain(locator_chain)

            # 提取动作的值（fill/press/select_option 的第一个参数）
            action_value = ''
            if action_name in ('fill', 'press', 'select_option'):
                action_value = _extract_first_string(action_args)

            actions.append({
                'index': index,
                'type': action_name,
                'locator_type': locator_type,
                'locator_value': locator_value,
                'name': name,
                'value': action_value,
                'raw': stripped,
            })
            index += 1
            continue

        # 无法识别的动作行 -> warning
        if 'page.' in stripped and stripped.endswith(')'):
            warnings.append(f'line {lineno}: 无法识别的动作行 - {stripped[:100]}')

    return actions, warnings


# ---------------------------------------------------------------------------
# 汇总解析
# ---------------------------------------------------------------------------

def parse_recording(content: str, filename: str = '') -> Dict:
    """完整解析录制脚本，返回全部字段。

    返回 dict:
      language, framework, start_url, normalized_content,
      locators_count, actions_count, actions, warnings
    """
    if not content or not content.strip():
        raise ValueError('脚本内容为空')

    language = detect_language(content, filename)
    framework = 'playwright'
    start_url = extract_start_url(content)
    locators = extract_locators(content)
    normalized = normalize_code(content, language)
    actions, action_warnings = extract_actions(content)

    warnings: List[str] = []
    if language == 'javascript':
        warnings.append('P1 服务端回放仅支持 Python 脚本，JavaScript 脚本将只入库不可直接回放。')
    if not start_url:
        warnings.append('未识别到起始 URL（page.goto），回放前请确认脚本可独立运行。')
    warnings.extend(action_warnings)

    return {
        'language': language,
        'framework': framework,
        'start_url': start_url,
        'normalized_content': normalized,
        'locators_count': len(locators),
        'actions_count': len(actions),
        'actions': actions,
        'warnings': warnings,
    }
