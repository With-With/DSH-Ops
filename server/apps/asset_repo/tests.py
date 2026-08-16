"""
asset_repo 单元测试：
- matching 三级匹配全覆盖
- URL 归一化
- {param} 占位匹配
- by-snapshot 匹配
- API CRUD
- 软删不可见
"""
from django.test import TestCase
from rest_framework.test import APIClient

from .matching import (
    _role_matches,
    match_element,
    match_page,
    normalize_url_pattern,
)
from .models import Element, PageObject


class NormalizeUrlTests(TestCase):
    def test_strip_query_and_hash(self):
        self.assertEqual(
            normalize_url_pattern("https://example.com/users?tab=1#section"),
            "https://example.com/users",
        )

    def test_trailing_slash_normalization(self):
        self.assertEqual(normalize_url_pattern("/users/"), "/users")
        self.assertEqual(normalize_url_pattern("/users"), "/users")
        self.assertEqual(normalize_url_pattern("/"), "/")

    def test_port_preserved(self):
        self.assertEqual(
            normalize_url_pattern("http://localhost:8080/users"),
            "http://localhost:8080/users",
        )

    def test_pure_path(self):
        self.assertEqual(normalize_url_pattern("/users/123/profile"), "/users/123/profile")

    def test_empty_url(self):
        self.assertEqual(normalize_url_pattern(""), "")


class MatchPageTests(TestCase):
    def setUp(self):
        PageObject.objects.create(name="用户列表", url_pattern="/users")
        PageObject.objects.create(
            name="用户详情", url_pattern="/users/{user_id}/profile"
        )
        PageObject.objects.create(
            name="产品详情", url_pattern="https://shop.example.com/products/{pid}"
        )

    def test_exact_match(self):
        page = match_page("/users")
        self.assertIsNotNone(page)
        self.assertEqual(page.name, "用户列表")

    def test_param_placeholder(self):
        page = match_page("/users/42/profile")
        self.assertIsNotNone(page)
        self.assertEqual(page.name, "用户详情")

    def test_param_no_slash_cross(self):
        """{param} 不能跨 /，多级路径不应误匹配。"""
        page = match_page("/users/42/extra/profile")
        self.assertIsNone(page)

    def test_full_url_with_port(self):
        page = match_page("https://shop.example.com/products/1001")
        self.assertIsNotNone(page)
        self.assertEqual(page.name, "产品详情")

    def test_no_match(self):
        page = match_page("/admin/dashboard")
        self.assertIsNone(page)

    def test_trailing_slash_input(self):
        """输入带 / 末尾也应匹配归一化后的模式。"""
        page = match_page("/users/")
        self.assertIsNotNone(page)
        self.assertEqual(page.name, "用户列表")


class RoleMatchTests(TestCase):
    def test_both_empty(self):
        self.assertTrue(_role_matches("", ""))

    def test_one_empty(self):
        self.assertTrue(_role_matches("button", ""))
        self.assertTrue(_role_matches("", "button"))

    def test_equal(self):
        self.assertTrue(_role_matches("button", "button"))

    def test_case_insensitive(self):
        self.assertTrue(_role_matches("Button", "button"))

    def test_not_equal(self):
        self.assertFalse(_role_matches("button", "link"))


class MatchElementTests(TestCase):
    def setUp(self):
        self.page_a = PageObject.objects.create(
            name="登录页", url_pattern="/login"
        )
        self.page_b = PageObject.objects.create(
            name="注册页", url_pattern="/register"
        )

        self.el_login_btn = Element.objects.create(
            page=self.page_a,
            name="登录按钮",
            role="button",
            candidates=[
                {"type": "role", "value": "button", "priority": 1, "robustness": 0.9}
            ],
            snapshot_hash="hash-login-btn",
            source="manual",
        )
        self.el_username = Element.objects.create(
            page=self.page_a,
            name="用户名输入框",
            role="textbox",
            candidates=[],
            source="recording",
        )
        self.el_reg_btn = Element.objects.create(
            page=self.page_b,
            name="登录按钮",
            role="button",
            candidates=[],
            source="manual",
        )
        self.el_login_link = Element.objects.create(
            page=self.page_b,
            name="登录链接",
            role="link",
            candidates=[],
            source="manual",
        )

    def test_t1_high_confidence_exact(self):
        """T1: 同页 + name 精确 + role 相等 → high"""
        result = match_element("/login", "登录按钮", "button")
        self.assertEqual(result["confidence"], "high")
        self.assertIsNotNone(result["match"])
        self.assertEqual(result["match"]["id"], self.el_login_btn.id)
        self.assertIn("T1", result["reason"])

    def test_t1_role_empty_on_either(self):
        """T1: role 一方为空也算兼容"""
        result = match_element("/login", "登录按钮", "")
        self.assertEqual(result["confidence"], "high")
        self.assertEqual(result["match"]["id"], self.el_login_btn.id)

    def test_t3_by_snapshot(self):
        """T3: snapshot_hash 命中 → high（跨页也可）"""
        result = match_element("/somewhere", "随便一个名", "", snapshot_hash="hash-login-btn")
        self.assertEqual(result["confidence"], "high")
        self.assertEqual(result["match"]["id"], self.el_login_btn.id)
        self.assertIn("by-snapshot", result["reason"])

    def test_t2_name_equal_different_page(self):
        """T2: name 相等但不同页 → medium

        场景：访问"找回密码页"（没有同名元素），找"登录按钮"。
        登录页和注册页都有"登录按钮"，但不在当前页 → medium。
        """
        # 创建一个没有"登录按钮"的页面
        page_c = PageObject.objects.create(
            name="找回密码页", url_pattern="/forgot-password"
        )
        result = match_element("/forgot-password", "登录按钮", "button")
        self.assertEqual(result["confidence"], "medium")
        self.assertIsNone(result["match"])
        self.assertTrue(len(result["similar"]) >= 1)
        # 候选里应该有登录页的登录按钮
        similar_ids = [s["id"] for s in result["similar"]]
        self.assertIn(self.el_login_btn.id, similar_ids)

    def test_t2_name_containment(self):
        """T2: name 互相包含 + role 相等 → medium"""
        # "登录" 包含在 "登录按钮" / "登录链接"
        result = match_element("/register", "登录", "")
        self.assertEqual(result["confidence"], "medium")
        self.assertTrue(len(result["similar"]) >= 2)

    def test_none_no_match(self):
        """完全不匹配 → none"""
        result = match_element("/login", "完全没见过的元素", "button")
        self.assertEqual(result["confidence"], "none")
        self.assertIsNone(result["match"])
        self.assertEqual(len(result["similar"]), 0)

    def test_empty_name(self):
        """空 name 直接返回 none"""
        result = match_element("/login", "", "button")
        self.assertEqual(result["confidence"], "none")

    def test_name_strip(self):
        """name 前后空格不影响匹配"""
        result = match_element("/login", "  登录按钮  ", "button")
        self.assertEqual(result["confidence"], "high")
        self.assertEqual(result["match"]["id"], self.el_login_btn.id)


class PageApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.page = PageObject.objects.create(name="首页", url_pattern="/")

    def test_list_pages(self):
        resp = self.client.get("/api/assets/pages/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["name"], "首页")

    def test_create_page(self):
        resp = self.client.post(
            "/api/assets/pages/",
            {"name": "关于页", "url_pattern": "/about"},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(PageObject.objects.count(), 2)

    def test_delete_page_soft(self):
        resp = self.client.delete(f"/api/assets/pages/{self.page.id}/")
        self.assertEqual(resp.status_code, 204)
        # 列表中不可见
        resp = self.client.get("/api/assets/pages/")
        self.assertEqual(resp.json()["count"], 0)
        # 数据库里还在（软删）
        self.assertTrue(PageObject.all_objects.filter(id=self.page.id).exists())


class ElementApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.page = PageObject.objects.create(name="首页", url_pattern="/")
        self.el = Element.objects.create(
            page=self.page, name="logo", role="img", candidates=[]
        )

    def test_list_elements_filter_by_page(self):
        resp = self.client.get(f"/api/assets/elements/?page_id={self.page.id}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["count"], 1)

    def test_list_elements_search(self):
        resp = self.client.get("/api/assets/elements/?search=logo")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["count"], 1)

    def test_create_element(self):
        resp = self.client.post(
            "/api/assets/elements/",
            {
                "page_id": self.page.id,
                "name": "搜索框",
                "role": "searchbox",
                "candidates": [{"type": "role", "value": "searchbox", "priority": 1, "robustness": 0.8}],
                "source": "manual",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(Element.objects.count(), 2)

    def test_delete_element_soft(self):
        resp = self.client.delete(f"/api/assets/elements/{self.el.id}/")
        self.assertEqual(resp.status_code, 204)
        # 列表中不可见
        resp = self.client.get("/api/assets/elements/")
        self.assertEqual(resp.json()["count"], 0)

    def test_query_endpoint_t1_match(self):
        """测试 query 接口：T1 高置信匹配"""
        resp = self.client.post(
            "/api/assets/elements/query/",
            {"page_url": "/", "name": "logo", "role": "img"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["confidence"], "high")
        self.assertEqual(data["match"]["id"], self.el.id)

    def test_query_endpoint_none(self):
        """测试 query 接口：完全不匹配"""
        resp = self.client.post(
            "/api/assets/elements/query/",
            {"page_url": "/", "name": "不存在的元素", "role": "button"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["confidence"], "none")
