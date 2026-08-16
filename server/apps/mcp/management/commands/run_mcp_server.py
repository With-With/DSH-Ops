"""
MCP server（stdio）：向 DSH 智能体暴露平台资产查询工具。

启动：python manage.py run_mcp_server

工具：
- query_elements(page_url, name, role="", snapshot_hash="") -> search-first 三级匹配结果
- list_pages() -> 页面对象摘要

注册进 dsh profile 的方式见 docs/skills-local/backend-agent-runtime/SKILL.md（P3 随 testhub profile 挂载）。
"""
import logging

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


def _matching():
    from apps.asset_repo import matching

    return matching


def _pages_qs():
    from apps.asset_repo.models import PageObject

    return PageObject.objects.all()


class Command(BaseCommand):
    help = "启动 elements query MCP server（stdio 协议），供 DSH 智能体调用"

    def handle(self, *args, **options):
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("dsh-ops-elements")

        @mcp.tool()
        def query_elements(
            page_url: str, name: str, role: str = "", snapshot_hash: str = ""
        ) -> dict:
            """按 search-first 三级匹配查询元素仓（high=直接复用，medium=人工裁决，none=可新建）。

            Args:
                page_url: 当前页面 URL（完整 URL 或纯 path）
                name: 元素语义名（如 "登录按钮"）
                role: ARIA 角色（可空）
                snapshot_hash: 元素快照哈希（可空，命中即 high）
            """
            return _matching().match_element(
                page_url=page_url,
                name=name,
                role=role,
                snapshot_hash=snapshot_hash or None,
            )

        @mcp.tool()
        def list_pages() -> list:
            """列出元素仓全部页面对象（id/name/url_pattern）。"""
            return list(
                _pages_qs().values("id", "name", "url_pattern", "created_at")
            )

        self.stdout.write(self.style.SUCCESS("MCP server 启动中 (stdio)..."))
        mcp.run()
