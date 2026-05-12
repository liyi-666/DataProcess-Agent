from skills.registry import register


def _safe_divide(numerator: int, denominator: int) -> float:
    """安全除法，避免除零错误"""
    return round(numerator / denominator, 4) if denominator > 0 else 0.0


def _compute_syntax_pass_rate(samples: list[dict]) -> float:
    """
    计算语法通过率
    近似实现：统计 parseOk=True 的样本比例
    """
    if not samples:
        return 0.0

    parse_ok_count = sum(1 for s in samples if s.get("parseOk") is True)
    return _safe_divide(parse_ok_count, len(samples))


def _compute_function_name_match_rate(samples: list[dict]) -> float:
    """
    计算函数名匹配率
    近似实现：统计有 functionName 字段的样本比例
    """
    if not samples:
        return 0.0

    has_function_name_count = sum(
        1 for s in samples
        if s.get("functionName") and isinstance(s.get("functionName"), str)
    )
    return _safe_divide(has_function_name_count, len(samples))


def _compute_return_annotation_rate(samples: list[dict]) -> float:
    """
    计算返回注解率
    近似实现：统计有 returnAnnotation 字段的样本比例
    """
    if not samples:
        return 0.0

    has_return_annotation_count = sum(
        1 for s in samples
        if s.get("returnAnnotation") and s.get("returnAnnotation") != "None"
    )
    return _safe_divide(has_return_annotation_count, len(samples))


@register("evaluate_data_quality")
def evaluate_data_quality(context: dict) -> dict:
    """生成质量指标。真实实现。"""
    samples: list[dict] = context.get("samples", [])
    metrics: dict = context.get("metrics", {})
    raw_count = context.get("rawSampleCount", 0)
    current_count = context.get("currentCount", len(samples))

    # 从 metrics 中提取 preprocess 阶段的统计信息
    ast_parse_success_count = metrics.get("astParseSuccessCount", 0)
    ast_parse_failed_count = metrics.get("astParseFailedCount", 0)
    empty_code_count = metrics.get("emptyCodeCount", 0)
    low_quality_docstring_count = metrics.get("lowQualityDocstringCount", 0)
    dedup_removed_count = metrics.get("dedupRemovedCount", 0)
    exact_dedup_removed_count = metrics.get("exactDedupRemovedCount", 0)
    ast_dedup_removed_count = metrics.get("astDedupRemovedCount", 0)

    # 计算保留率
    retain_rate = _safe_divide(current_count, raw_count)

    # 计算语法通过率（基于最终样本）
    syntax_pass_rate = _compute_syntax_pass_rate(samples)

    # 从 metrics 中获取 docstring 覆盖率（由 compute_dataset_profile 计算）
    docstring_coverage = metrics.get("docstringCoverage", 0.0)

    # 计算函数名匹配率
    function_name_match_rate = _compute_function_name_match_rate(samples)

    # 计算返回注解率
    return_annotation_rate = _compute_return_annotation_rate(samples)

    quality_metrics = {
        "retainRate": retain_rate,
        "astParseSuccessCount": ast_parse_success_count,
        "astParseFailedCount": ast_parse_failed_count,
        "emptyCodeCount": empty_code_count,
        "lowQualityDocstringCount": low_quality_docstring_count,
        "dedupRemovedCount": dedup_removed_count,
        "exactDedupRemovedCount": exact_dedup_removed_count,
        "astDedupRemovedCount": ast_dedup_removed_count,
        "syntaxPassRate": syntax_pass_rate,
        "docstringCoverage": docstring_coverage,
        "functionNameMatchRate": function_name_match_rate,
        "returnAnnotationRate": return_annotation_rate,
    }

    return {
        "inputCount": current_count,
        "outputCount": current_count,
        "removedCount": 0,
        "qualityMetrics": quality_metrics,
        "status": "success",
        "message": f"质量评估完成，保留率 {retain_rate}，语法通过率 {syntax_pass_rate}",
    }

