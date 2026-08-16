"""
seed_ai_providers：从本地密钥文件导入 AI 提供方配置。

文件：server/ai_providers.local.json（已 gitignore，禁止上传 GitHub）。
用法：python manage.py seed_ai_providers

导入规则：
- 按 name 幂等（已存在则更新 base_url/model/api_key/is_default）
- api_key 经 Fernet 加密落库，界面只回掩码
- 未提供该文件时输出提示并跳过（不报错）
"""
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.ai_config.crypto import encrypt_key, mask_key
from apps.ai_config.models import AIProviderConfig


class Command(BaseCommand):
    help = "从 server/ai_providers.local.json 导入 AI 提供方配置（密钥加密落库）"

    def handle(self, *args, **options):
        path = Path(settings.DSHOPS_REPO_ROOT) / "server" / "ai_providers.local.json"
        if not path.exists():
            self.stdout.write(
                self.style.WARNING(
                    "未找到 ai_providers.local.json（已 gitignore）。"
                    "参考 server/ai_providers.local.json.example 创建后重试。"
                )
            )
            return

        data = json.loads(path.read_text(encoding="utf-8"))
        providers = data.get("providers", [])
        created, updated = 0, 0

        for item in providers:
            name = (item.get("name") or "").strip()
            if not name:
                continue
            defaults = {
                "provider": item.get("provider", "custom"),
                "base_url": item.get("base_url", ""),
                "model_name": item.get("model_name", ""),
                "enabled": True,
            }
            api_key = item.get("api_key") or ""
            if api_key and not api_key.startswith("sk-替换"):
                defaults["api_key_encrypted"] = encrypt_key(api_key)
                defaults["api_key_mask"] = mask_key(api_key)

            obj, is_new = AIProviderConfig.objects.update_or_create(
                name=name, defaults=defaults
            )
            if is_new:
                created += 1
            else:
                updated += 1
            self.stdout.write(
                f"  {name}: {'新建' if is_new else '更新'} "
                f"(mask={obj.api_key_mask or '未设置'})"
            )

        # 默认互斥：若任一配置标记 is_default，清除其余
        default_names = [p["name"] for p in providers if p.get("is_default")]
        if default_names:
            AIProviderConfig.objects.exclude(name__in=default_names).update(is_default=False)

        self.stdout.write(self.style.SUCCESS(f"完成：新建 {created}，更新 {updated}"))
