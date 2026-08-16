"""
契约校验：基于 jsonschema Draft202012 校验 POM / Matrix 文档。

Schema 文件位于 <repo>/contracts/*.schema.json，
validator 做模块级缓存，避免每次调用都读文件 + 编译。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Tuple, List

from django.conf import settings

import jsonschema
from jsonschema import Draft202012Validator


# ---------------------------------------------------------------------------
# 模块级缓存
# ---------------------------------------------------------------------------

_SCHEMA_DIR: Path | None = None
_VALIDATORS: dict[str, Draft202012Validator] = {}


def _schema_dir() -> Path:
    global _SCHEMA_DIR
    if _SCHEMA_DIR is None:
        _SCHEMA_DIR = Path(settings.DSHOPS_REPO_ROOT) / "contracts"
    return _SCHEMA_DIR


def _load_schema(name: str) -> dict:
    """加载指定名称的 schema JSON。"""
    path = _schema_dir() / f"{name}.schema.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _get_validator(name: str) -> Draft202012Validator:
    """获取（缓存）指定 schema 的 Draft202012Validator。"""
    if name not in _VALIDATORS:
        schema = _load_schema(name)
        validator = Draft202012Validator(schema)
        _VALIDATORS[name] = validator
    return _VALIDATORS[name]


# ---------------------------------------------------------------------------
# 对外 API
# ---------------------------------------------------------------------------

def _error_to_dict(err: jsonschema.ValidationError) -> dict:
    """把 ValidationError 转为可序列化 dict。"""
    return {
        "path": list(err.absolute_path),
        "message": err.message,
        "validator": err.validator,
    }


def validate_pom(doc: dict) -> Tuple[bool, List[dict]]:
    """校验 POM 文档。

    Returns:
        (is_valid, errors) — errors 为 JSON 可序列化的错误列表。
    """
    validator = _get_validator("pom")
    errors = [_error_to_dict(e) for e in validator.iter_errors(doc)]
    return (len(errors) == 0), errors


def validate_matrix(doc: dict) -> Tuple[bool, List[dict]]:
    """校验 Matrix 文档。

    Returns:
        (is_valid, errors) — errors 为 JSON 可序列化的错误列表。
    """
    validator = _get_validator("matrix")
    errors = [_error_to_dict(e) for e in validator.iter_errors(doc)]
    return (len(errors) == 0), errors
