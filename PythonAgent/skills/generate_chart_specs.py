from skills.registry import register


def _build_sample_count_chart(raw_count: int, final_count: int) -> dict:
    """构建处理前后样本数量对比图"""
    return {
        "chartId": "sample_count_compare",
        "chartType": "bar",
        "title": "处理前后样本数量对比",
        "xAxis": ["原始样本", "最终样本"],
        "series": [{"name": "样本数", "data": [raw_count, final_count]}],
    }


def _build_filter_reasons_chart(metrics: dict) -> dict:
    """构建过滤原因统计图"""
    empty_code_count = metrics.get("emptyCodeCount", 0)
    ast_parse_failed_count = metrics.get("astParseFailedCount", 0)
    low_quality_docstring_count = metrics.get("lowQualityDocstringCount", 0)

    return {
        "chartId": "filter_reasons",
        "chartType": "bar",
        "title": "过滤原因统计",
        "xAxis": ["空代码", "AST 解析失败", "低质量 docstring"],
        "series": [
            {
                "name": "过滤数量",
                "data": [empty_code_count, ast_parse_failed_count, low_quality_docstring_count],
            }
        ],
    }


def _build_dedup_results_chart(metrics: dict) -> dict:
    """构建去重结果统计图"""
    exact_dedup_removed = metrics.get("exactDedupRemovedCount", 0)
    ast_dedup_removed = metrics.get("astDedupRemovedCount", 0)

    return {
        "chartId": "dedup_results",
        "chartType": "bar",
        "title": "去重结果统计",
        "xAxis": ["精确去重", "AST 去重"],
        "series": [
            {
                "name": "去重数量",
                "data": [exact_dedup_removed, ast_dedup_removed],
            }
        ],
    }


def _build_quality_metrics_chart(metrics: dict) -> dict:
    """构建数据质量指标图"""
    syntax_pass_rate = metrics.get("syntaxPassRate", 0.0)
    docstring_coverage = metrics.get("docstringCoverage", 0.0)
    function_name_match_rate = metrics.get("functionNameMatchRate", 0.0)
    return_annotation_rate = metrics.get("returnAnnotationRate", 0.0)

    return {
        "chartId": "quality_metrics",
        "chartType": "bar",
        "title": "数据质量指标",
        "xAxis": ["语法通过率", "docstring 覆盖率", "函数名匹配率", "返回注解率"],
        "series": [
            {
                "name": "比率",
                "data": [
                    syntax_pass_rate,
                    docstring_coverage,
                    function_name_match_rate,
                    return_annotation_rate,
                ],
            }
        ],
    }


@register("generate_chart_specs")
def generate_chart_specs(context: dict) -> dict:
    """生成前端图表配置数据。真实实现。"""
    metrics: dict = context.get("metrics", {})
    raw_count = context.get("rawSampleCount", 0)
    current_count = context.get("currentCount", 0)

    charts = []

    # 图表 1: 处理前后样本数量对比
    charts.append(_build_sample_count_chart(raw_count, current_count))

    # 图表 2: 过滤原因统计（如果有过滤数据）
    if any(
        metrics.get(k, 0) > 0
        for k in ["emptyCodeCount", "astParseFailedCount", "lowQualityDocstringCount"]
    ):
        charts.append(_build_filter_reasons_chart(metrics))

    # 图表 3: 去重结果统计（如果有去重数据）
    if any(metrics.get(k, 0) > 0 for k in ["exactDedupRemovedCount", "astDedupRemovedCount"]):
        charts.append(_build_dedup_results_chart(metrics))

    # 图表 4: 数据质量指标
    charts.append(_build_quality_metrics_chart(metrics))

    return {
        "inputCount": current_count,
        "outputCount": current_count,
        "removedCount": 0,
        "chartSpecs": charts,
        "status": "success",
        "message": f"图表配置生成完成，共 {len(charts)} 个图表",
    }

