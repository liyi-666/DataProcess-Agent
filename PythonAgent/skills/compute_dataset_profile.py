from skills.registry import register


def _compute_avg_length(samples: list[dict], field: str) -> float:
    """计算指定字段的平均长度"""
    if not samples:
        return 0.0

    total_length = 0
    valid_count = 0

    for sample in samples:
        value = sample.get(field)
        if value and isinstance(value, str):
            total_length += len(value)
            valid_count += 1

    return round(total_length / valid_count, 2) if valid_count > 0 else 0.0


def _compute_docstring_coverage(samples: list[dict], doc_field: str) -> float:
    """计算 docstring 覆盖率"""
    if not samples:
        return 0.0

    has_docstring_count = 0

    for sample in samples:
        # 检查多个可能的 docstring 字段（优先级从高到低）
        docstring = (
            sample.get(doc_field)  # 用户指定的字段
            or sample.get("docstringInCode")  # AST 提取的 docstring
            or sample.get("docstring")  # 默认字段
            or sample.get("comment")  # 备选字段
        )
        if docstring and isinstance(docstring, str) and docstring.strip():
            has_docstring_count += 1

    return round(has_docstring_count / len(samples), 4) if samples else 0.0


@register("compute_dataset_profile")
def compute_dataset_profile(context: dict) -> dict:
    """生成数据画像统计。真实实现。"""
    samples: list[dict] = context.get("samples", [])
    schema: dict = context.get("schema", {})
    raw_count = context.get("rawSampleCount", 0)
    current_count = context.get("currentCount", len(samples))

    code_field = schema.get("codeField", "code")
    doc_field = schema.get("docstringField", "docstring")

    # 计算平均代码长度
    avg_code_length = _compute_avg_length(samples, code_field)

    # 计算平均 docstring 长度
    avg_docstring_length = _compute_avg_length(samples, doc_field)

    # 计算 docstring 覆盖率
    docstring_coverage = _compute_docstring_coverage(samples, doc_field)

    profile = {
        "rawSampleCount": raw_count,
        "finalSampleCount": current_count,
        "avgCodeLength": avg_code_length,
        "avgDocstringLength": avg_docstring_length,
        "docstringCoverage": docstring_coverage,
    }

    return {
        "inputCount": current_count,
        "outputCount": current_count,
        "removedCount": 0,
        "profile": profile,
        "status": "success",
        "message": f"数据画像统计完成，平均代码长度 {avg_code_length}，docstring 覆盖率 {docstring_coverage}",
    }

