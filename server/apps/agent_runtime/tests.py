"""
agent_runtime / reviews / mcp 测试：
- extract_json 三态（围栏/裸 JSON/垃圾）
- gateway mock 模式：fixture 返回 + AgentInvocation 落库 + mock 标志
- 契约校验：mock fixture 正例 + 篡改反例
- API：invocations/drafts/gateway-test
- reviews：approve/reject/409
- MCP：工具函数直调（search-first 语义）
"""
import json
from pathlib import Path

from django.test import TestCase
from rest_framework.test import APIClient

from apps.agent_runtime.contracts import validate_matrix, validate_pom
from apps.agent_runtime.gateway import AgentGateway, extract_json
from apps.agent_runtime.models import AgentInvocation, ArtifactDraft


FIXTURES = Path(__file__).resolve().parent / "fixtures"


class ExtractJsonTests(TestCase):
    def test_fence(self):
        text = '前言\n```json\n{"a": 1}\n```\n后语'
        self.assertEqual(extract_json(text), {"a": 1})

    def test_bare_object(self):
        text = '结果如下：{"x": [1, 2], "y": {"z": true}} 完毕'
        self.assertEqual(extract_json(text), {"x": [1, 2], "y": {"z": True}})

    def test_nested_braces(self):
        text = '{"a": {"b": {"c": 1}}, "d": 2} tail'
        self.assertEqual(extract_json(text), {"a": {"b": {"c": 1}}, "d": 2})

    def test_garbage(self):
        self.assertIsNone(extract_json("完全没有 JSON 的内容"))
        self.assertIsNone(extract_json(""))
        self.assertIsNone(extract_json("{broken"))


class GatewayMockTests(TestCase):
    def setUp(self):
        self.gw = AgentGateway()
        self.gw.mode = "mock"

    def test_mock_pom_stage(self):
        inv = self.gw.run_stage("a1_extract", "指令", task_set_id=7, recording_id=3)
        self.assertEqual(inv.status, "success")
        self.assertTrue(inv.mock)
        self.assertEqual(inv.task_set_id, 7)
        self.assertEqual(inv.recording_id, 3)
        self.assertIsNotNone(inv.parsed_json)
        self.assertEqual(inv.parsed_json["schema_version"], "1.0.0-dev")
        self.assertGreaterEqual(len(inv.parsed_json["elements"]), 3)
        # 落库
        self.assertTrue(AgentInvocation.objects.filter(pk=inv.pk).exists())

    def test_mock_matrix_stage(self):
        inv = self.gw.run_stage("a2_design", "指令")
        self.assertEqual(inv.status, "success")
        self.assertIn("schema_version", inv.parsed_json)

    def test_mock_unknown_stage(self):
        inv = self.gw.run_stage("bogus", "指令")
        self.assertEqual(inv.status, "success")
        self.assertEqual(inv.parsed_json, {"ack": True, "stage": "bogus"})

    def test_extract_json_reuses_fixture_content(self):
        # fixture 本身应能通过契约校验（防契约漂移）
        pom = json.loads((FIXTURES / "mock_pom.json").read_text(encoding="utf-8"))
        mat = json.loads((FIXTURES / "mock_matrix.json").read_text(encoding="utf-8"))
        self.assertTrue(validate_pom(pom)[0])
        self.assertTrue(validate_matrix(mat)[0])


class ContractValidationTests(TestCase):
    def test_pom_negative(self):
        valid, _ = validate_pom({"schema_version": "1.0.0-dev"})
        self.assertFalse(valid)

    def test_pom_wrong_version_const(self):
        doc = json.loads((FIXTURES / "mock_pom.json").read_text(encoding="utf-8"))
        doc["schema_version"] = "9.9.9"
        valid, errors = validate_pom(doc)
        self.assertFalse(valid)
        self.assertTrue(any("schema_version" in str(e) for e in errors))

    def test_matrix_negative(self):
        valid, _ = validate_matrix({"foo": 1})
        self.assertFalse(valid)


class AgentRuntimeApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.gw = AgentGateway()
        self.gw.mode = "mock"
        self.inv = self.gw.run_stage("a1_extract", "测试指令")
        self.draft = ArtifactDraft.objects.create(
            task_set_id=1,
            kind="pom",
            content={"schema_version": "1.0.0-dev"},
            schema_version="1.0.0-dev",
            valid=True,
            invocation_id=self.inv.pk,
        )

    def test_invocations_list(self):
        resp = self.client.get("/api/agent/invocations/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["count"], 1)

    def test_drafts_list_and_filter(self):
        resp = self.client.get("/api/agent/drafts/?kind=pom")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["count"], 1)
        resp = self.client.get("/api/agent/drafts/?kind=matrix")
        self.assertEqual(resp.json()["count"], 0)

    def test_draft_detail(self):
        resp = self.client.get(f"/api/agent/drafts/{self.draft.pk}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["kind"], "pom")

    def test_gateway_test_mock(self):
        resp = self.client.post(
            "/api/agent/gateway/test/",
            {"stage": "a1_extract", "instruction": "hi", "mock": True},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["mock"])
        self.assertEqual(resp.json()["status"], "success")


class ReviewsApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.draft = ArtifactDraft.objects.create(
            task_set_id=2,
            kind="matrix",
            content={"schema_version": "0.1.0"},
            schema_version="0.1.0",
            valid=True,
        )

    def test_reviews_list(self):
        resp = self.client.get("/api/reviews/drafts/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["count"], 1)

    def test_approve(self):
        resp = self.client.post(
            f"/api/reviews/drafts/{self.draft.pk}/approve/",
            {"note": "批准"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["status"], "approved")
        self.assertEqual(body["review_note"], "批准")
        self.assertIsNotNone(body["reviewed_at"])

    def test_reject_then_409(self):
        self.client.post(f"/api/reviews/drafts/{self.draft.pk}/reject/", format="json")
        resp = self.client.post(f"/api/reviews/drafts/{self.draft.pk}/approve/", format="json")
        self.assertEqual(resp.status_code, 409)

    def test_review_missing_draft(self):
        resp = self.client.post("/api/reviews/drafts/99999/approve/", format="json")
        self.assertEqual(resp.status_code, 404)


class McpToolTests(TestCase):
    """MCP 工具函数直调（等价于 tools/call 的服务端实现）。"""

    def setUp(self):
        from apps.asset_repo.models import Element, PageObject

        self.page = PageObject.objects.create(
            name="登录页", url_pattern="http://127.0.0.1:8001/api/demo/login/"
        )
        Element.objects.create(
            page=self.page, name="登录", role="button", candidates=[], source="recording"
        )

    def test_query_elements_high(self):
        from apps.mcp.management.commands.run_mcp_server import _matching

        result = _matching().match_element(
            page_url="http://127.0.0.1:8001/api/demo/login/",
            name="登录",
            role="button",
        )
        self.assertEqual(result["confidence"], "high")

    def test_query_elements_none(self):
        from apps.mcp.management.commands.run_mcp_server import _matching

        result = _matching().match_element(
            page_url="http://127.0.0.1:8001/api/demo/login/", name="不存在的按钮"
        )
        self.assertEqual(result["confidence"], "none")
