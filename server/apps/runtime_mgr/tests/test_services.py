"""
RuntimeMgr 单元测试。

覆盖范围：
1. detect_runtime 的版本解析（mock subprocess.run）
2. 版本漂移判定
3. 软删后列表不可见
4. delete_runtime 拒绝条件（mock can_delete=False 时）
5. AuditLog 写入
"""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import TestCase

from apps.runtime_mgr.models import RuntimeInstance
from apps.runtime_mgr import services


class TestParseVersion(TestCase):
    """版本号解析测试。"""

    def test_parse_dsh_version_rc_format(self):
        """测试 dsh/0.1.0-rc.6 格式。"""
        stdout = "dsh/0.1.0-rc.6 win32-x64 node-v20.18.0"
        self.assertEqual(services._parse_dsh_version(stdout), "0.1.0-rc.6")

    def test_parse_dsh_version_plain(self):
        """测试纯版本号格式。"""
        stdout = "0.2.1"
        self.assertEqual(services._parse_dsh_version(stdout), "0.2.1")

    def test_parse_dsh_version_with_v_prefix(self):
        """测试 v 前缀格式。"""
        stdout = "v1.0.0"
        self.assertEqual(services._parse_dsh_version(stdout), "1.0.0")

    def test_parse_dsh_version_empty(self):
        """测试空输出。"""
        self.assertEqual(services._parse_dsh_version(""), "")
        self.assertEqual(services._parse_dsh_version(None), "")

    def test_parse_node_version(self):
        """测试 node -v 输出解析。"""
        self.assertEqual(services._parse_node_version("v20.18.0"), "20.18.0")
        self.assertEqual(services._parse_node_version("v18.20.3"), "18.20.3")
        self.assertEqual(services._parse_node_version(""), "")


class TestDetectRuntime(TestCase):
    """detect_runtime 服务测试。"""

    def _make_fake_dsh(self, tmpdir):
        """在 tmpdir 下创建假的 dsh 可执行文件路径。"""
        if os.name == "nt":
            bin_dir = Path(tmpdir) / "node_modules" / ".bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            dsh_bin = bin_dir / "dsh.cmd"
            dsh_bin.write_text("@echo off\necho dsh/0.1.0-rc.6 win32-x64 node-v20.18.0", encoding="utf-8")
        else:
            bin_dir = Path(tmpdir) / "node_modules" / ".bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            dsh_bin = bin_dir / "dsh"
            dsh_bin.write_text("#!/bin/sh\necho 'dsh/0.1.0-rc.6 linux-x64 node-v20.18.0'", encoding="utf-8")
            dsh_bin.chmod(0o755)
        return str(dsh_bin)

    @patch("apps.runtime_mgr.services.shutil.which")
    @patch("apps.runtime_mgr.services._run_cmd")
    def test_detect_global_path(self, mock_run, mock_which):
        """测试全局 PATH 回退路径。"""
        mock_which.return_value = "/usr/local/bin/dsh"

        def side_effect(cmd, **kwargs):
            if "dsh" in str(cmd[0]) and "-V" in cmd:
                return 0, "dsh/0.1.0-rc.6 linux-x64 node-v20.18.0", ""
            if cmd[0] == "node":
                return 0, "v20.18.0", ""
            return 1, "", "not found"

        mock_run.side_effect = side_effect

        # 强制本地 runtime 不存在，走全局 PATH 分支
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(services, "_repo_root", return_value=Path(tmpdir)):
                result = services.detect_runtime()
                self.assertEqual(result["detect_source"], "global-which")
                self.assertEqual(result["version"], "0.1.0-rc.6")
                self.assertEqual(result["node_version"], "20.18.0")

    @patch("apps.runtime_mgr.services.shutil.which")
    @patch("apps.runtime_mgr.services._run_cmd")
    def test_detect_not_found(self, mock_run, mock_which):
        """测试 dsh 未找到时返回 error 状态。"""
        mock_which.return_value = None
        # 本地 runtime 目录不存在的情况下，应走 not-found

        # 让 _repo_root 指向一个不存在 runtime 的临时目录
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(services, "_repo_root", return_value=Path(tmpdir)):
                result = services.detect_runtime()
                self.assertEqual(result["detect_source"], "not-found")
                self.assertEqual(result["status"], "error")
                self.assertIn("未找到", result["status_detail"])

    @patch("apps.runtime_mgr.services.shutil.which")
    @patch("apps.runtime_mgr.services._run_cmd")
    @patch("apps.runtime_mgr.services._load_pinned_version")
    def test_version_drift_warning(self, mock_pinned, mock_run, mock_which):
        """测试版本漂移：实际版本与契约版本不一致 => warning。"""
        mock_which.return_value = None  # 不走全局
        mock_pinned.return_value = "0.2.0"  # 契约要求 0.2.0

        def side_effect(cmd, **kwargs):
            if "dsh" in str(cmd[0]) and "-V" in cmd:
                return 0, "dsh/0.1.0-rc.6 win32-x64 node-v20.18.0", ""
            if cmd[0] == "node":
                return 0, "v20.18.0", ""
            return 1, "", "not found"

        mock_run.side_effect = side_effect

        with tempfile.TemporaryDirectory() as tmpdir:
            runtime_dir = Path(tmpdir) / "agent" / "runtime"
            bin_dir = runtime_dir / "node_modules" / ".bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            dsh_bin = bin_dir / ("dsh.cmd" if os.name == "nt" else "dsh")
            dsh_bin.write_text("fake", encoding="utf-8")

            # 创建 home 目录
            home_dir = Path(tmpdir) / "agent" / "home"
            home_dir.mkdir(parents=True, exist_ok=True)

            with patch.object(services, "_repo_root", return_value=Path(tmpdir)):
                result = services.detect_runtime()
                self.assertEqual(result["detect_source"], "local-runtime")
                self.assertTrue(result["version_drift"])
                self.assertEqual(result["status"], "warning")
                self.assertIn("版本漂移", result["status_detail"])


class TestSoftDelete(TestCase):
    """软删除测试。"""

    def setUp(self):
        self.instance = RuntimeInstance.objects.create(
            name="test-runtime",
            version="1.0.0",
            status="healthy",
        )

    def test_soft_delete_hides_from_default_manager(self):
        """软删后默认 manager 不可见。"""
        self.assertEqual(RuntimeInstance.objects.count(), 1)
        self.instance.delete()
        self.assertEqual(RuntimeInstance.objects.count(), 0)
        # all_objects 仍可见
        self.assertEqual(RuntimeInstance.all_objects.count(), 1)

    def test_soft_delete_sets_flag(self):
        """软删后 is_deleted=True, deleted_at 非空。"""
        self.instance.delete()
        refreshed = RuntimeInstance.all_objects.get(pk=self.instance.pk)
        self.assertTrue(refreshed.is_deleted)
        self.assertIsNotNone(refreshed.deleted_at)

    def test_restore(self):
        """恢复后可被默认 manager 查到。"""
        self.instance.delete()
        self.assertEqual(RuntimeInstance.objects.count(), 0)
        self.instance.restore()
        self.assertEqual(RuntimeInstance.objects.count(), 1)
        self.assertFalse(self.instance.is_deleted)
        self.assertIsNone(self.instance.deleted_at)


class TestDeleteRuntime(TestCase):
    """delete_runtime 服务测试。"""

    def setUp(self):
        self.instance = RuntimeInstance.objects.create(
            name="delete-test",
            version="1.0.0",
            status="healthy",
        )
        self.user = User.objects.create_user(username="tester", password="12345")

    def test_soft_delete_default(self):
        """默认软删，写审计日志。"""
        from apps.core.models import AuditLog

        success, reason = services.delete_runtime(self.instance, user=self.user)
        self.assertTrue(success)
        self.assertEqual(reason, "")
        self.assertTrue(RuntimeInstance.all_objects.get(pk=self.instance.pk).is_deleted)

        # 审计日志存在
        logs = AuditLog.objects.filter(action="runtime.delete")
        self.assertEqual(logs.count(), 1)
        log = logs.first()
        self.assertEqual(log.created_by, self.user)
        self.assertEqual(log.detail["instance_id"], self.instance.id)
        self.assertFalse(log.detail["physical"])

    @patch("apps.runtime_mgr.services.can_delete")
    def test_delete_rejected_when_can_delete_false(self, mock_can_delete):
        """can_delete 返回 False 时拒绝删除。"""
        mock_can_delete.return_value = (False, "存在运行中的任务集")

        success, reason = services.delete_runtime(self.instance)
        self.assertFalse(success)
        self.assertEqual(reason, "存在运行中的任务集")
        # 实例未被删除
        self.assertFalse(RuntimeInstance.all_objects.get(pk=self.instance.pk).is_deleted)

    def test_physical_delete_removes_dir(self):
        """physical=True 时删除 runtime_dir。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            runtime_dir = Path(tmpdir) / "my-runtime"
            runtime_dir.mkdir()
            (runtime_dir / "file.txt").write_text("test", encoding="utf-8")

            self.instance.runtime_dir = str(runtime_dir)
            self.instance.save()

            success, _ = services.delete_runtime(self.instance, physical=True)
            self.assertTrue(success)
            self.assertFalse(runtime_dir.exists())

    def test_delete_home_requires_physical(self):
        """delete_home=True 且 physical=True 时才删 home_dir。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            home_dir = Path(tmpdir) / "my-home"
            home_dir.mkdir()
            (home_dir / "config.json").write_text("{}", encoding="utf-8")

            self.instance.home_dir = str(home_dir)
            self.instance.save()

            # 不 physical 时不删 home
            success, _ = services.delete_runtime(self.instance, physical=False, delete_home=True)
            self.assertTrue(success)
            self.assertTrue(home_dir.exists())

            # 恢复并物理删除
            self.instance.restore()
            success, _ = services.delete_runtime(self.instance, physical=True, delete_home=True)
            self.assertTrue(success)
            self.assertFalse(home_dir.exists())

    def test_audit_log_written_on_delete(self):
        """删除操作必须写 AuditLog。"""
        from apps.core.models import AuditLog

        pre_count = AuditLog.objects.count()
        services.delete_runtime(self.instance, user=self.user)
        post_count = AuditLog.objects.count()
        self.assertEqual(post_count - pre_count, 1)

        log = AuditLog.objects.latest("created_at")
        self.assertEqual(log.action, "runtime.delete")
        self.assertIn("RuntimeInstance:", log.target)
        self.assertEqual(log.created_by, self.user)


class TestHealthCheck(TestCase):
    """健康检查测试。"""

    @patch("apps.runtime_mgr.services._run_cmd")
    @patch("apps.runtime_mgr.services._list_profiles")
    def test_health_check_success(self, mock_profiles, mock_run):
        """exit 0 时状态变为 healthy。"""
        instance = RuntimeInstance.objects.create(
            name="hc-test",
            dsh_bin_path="/fake/dsh",
            home_dir="/fake/home",
            status="unknown",
        )
        mock_profiles.return_value = ["default"]
        mock_run.return_value = (0, "config: {}", "")

        with patch.object(Path, "is_file", return_value=True):
            detail = services.health_check(instance)

        self.assertTrue(detail["passed"])
        self.assertEqual(detail["exit_code"], 0)
        self.assertEqual(detail["profile_used"], "default")
        instance.refresh_from_db()
        self.assertEqual(instance.status, "healthy")
        self.assertIsNotNone(instance.last_check_at)

    @patch("apps.runtime_mgr.services._run_cmd")
    @patch("apps.runtime_mgr.services._list_profiles")
    def test_health_check_failure(self, mock_profiles, mock_run):
        """非零 exit 时状态变为 error。"""
        instance = RuntimeInstance.objects.create(
            name="hc-test-fail",
            dsh_bin_path="/fake/dsh",
            home_dir="/fake/home",
            status="healthy",
        )
        mock_profiles.return_value = []
        mock_run.return_value = (1, "", "some error message")

        with patch.object(Path, "is_file", return_value=True):
            detail = services.health_check(instance)

        self.assertFalse(detail["passed"])
        self.assertEqual(detail["exit_code"], 1)
        # 无 profile 时回退 headless（dsh 从模板自动初始化），不再是 "(none)"
        self.assertEqual(detail["profile_used"], "headless(auto-init)")
        # 回退分支构造的命令必须显式带 --profile，否则 dsh CLI 拒绝执行
        built_cmd = mock_run.call_args[0][0]
        self.assertIn("--profile", built_cmd)
        self.assertIn("headless", built_cmd)
        instance.refresh_from_db()
        self.assertEqual(instance.status, "error")
        self.assertIn("some error", instance.notes)

    def test_health_check_missing_binary(self):
        """dsh 二进制不存在时直接 error。"""
        instance = RuntimeInstance.objects.create(
            name="hc-test-missing",
            dsh_bin_path="/nonexistent/dsh",
            home_dir="",
            status="unknown",
        )
        detail = services.health_check(instance)
        self.assertFalse(detail["passed"])
        self.assertIn("不存在", detail["stderr"])
        instance.refresh_from_db()
        self.assertEqual(instance.status, "error")
