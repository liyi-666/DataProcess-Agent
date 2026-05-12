from skills.registry import register

# 长度阈值
CODE_MIN_LEN = 10
CODE_MAX_LEN = 8000
DOCSTRING_MAX_LEN = 2000


def _is_empty_or_whitespace(text) -> bool:
    """检查是否为空或全空白"""
    if text is None:
        return True
    if not isinstance(text, str):
        return True
    return len(text.strip()) == 0


def _check_invalid_reason(sample: dict, code_field: str, doc_field: str) -> str | None:
    """检查样本是否无效，返回第一个命中的原因，None 表示有效"""
    code = sample.get(code_field)

    # 1. code 为空或全空白
    if _is_empty_or_whitespace(code):
        return "empty_code"

    # 2. parseOk = false
    if sample.get("parseOk") is False:
        return "ast_parse_failed"

    # 3. functionName 缺失（如果已经是函数级样本）
    # 判断依据：如果样本有 parseOk 字段且为 True，说明经过了 extract_function_structure
    if sample.get("parseOk") is True:
        func_name = sample.get("functionName")
        if not func_name or (isinstance(func_name, str) and not func_name.strip()):
            return "missing_function_name"

    # 4. code 长度过短
    code_len = len(code)
    if code_len < CODE_MIN_LEN:
        return "code_too_short"

    # 5. code 长度过长
    if code_len > CODE_MAX_LEN:
        return "code_too_long"

    # 6. docstring 长度过长（如果存在）
    if doc_field:
        docstring = sample.get(doc_field)
        if docstring and isinstance(docstring, str) and len(docstring) > DOCSTRING_MAX_LEN:
            return "docstring_too_long"

    return None


@register("filter_invalid_samples")
def filter_invalid_samples(context: dict) -> dict:
    """过滤空值、长度异常、语法错误样本。真实实现。"""
    samples: list[dict] = context.get("samples", [])
    schema: dict = context.get("schema", {})
    code_field = schema.get("codeField", "")
    doc_field = schema.get("docstringField")

    if not samples or not code_field:
        n = len(samples)
        return {
            "samples": samples,
            "inputCount": n,
            "outputCount": n,
            "removedCount": 0,
            "emptyCodeCount": 0,
            "astParseFailedCount": 0,
            "missingFunctionNameCount": 0,
            "codeTooShortCount": 0,
            "codeTooLongCount": 0,
            "docstringTooLongCount": 0,
            "status": "success",
            "message": "无需过滤（字段未配置）",
        }

    input_count = len(samples)
    valid_samples = []
    stats = {
        "empty_code": 0,
        "ast_parse_failed": 0,
        "missing_function_name": 0,
        "code_too_short": 0,
        "code_too_long": 0,
        "docstring_too_long": 0,
    }

    for sample in samples:
        reason = _check_invalid_reason(sample, code_field, doc_field)
        if reason:
            stats[reason] += 1
        else:
            valid_samples.append(sample)

    output_count = len(valid_samples)
    removed_count = input_count - output_count

    # 调试输出
    print(f"\n[DEBUG] filter_invalid_samples:")
    print(f"  输入样本: {input_count}")
    print(f"  输出样本: {output_count}")
    print(f"  过滤样本: {removed_count}")
    print(f"  过滤原因统计:")
    for reason, count in stats.items():
        if count > 0:
            print(f"    {reason}: {count}")
    print()

    return {
        "samples": valid_samples,
        "inputCount": input_count,
        "outputCount": output_count,
        "removedCount": removed_count,
        "emptyCodeCount": stats["empty_code"],
        "astParseFailedCount": stats["ast_parse_failed"],
        "missingFunctionNameCount": stats["missing_function_name"],
        "codeTooShortCount": stats["code_too_short"],
        "codeTooLongCount": stats["code_too_long"],
        "docstringTooLongCount": stats["docstring_too_long"],
        "status": "success",
        "message": f"无效样本过滤完成，保留 {output_count}/{input_count} 条",
    }
