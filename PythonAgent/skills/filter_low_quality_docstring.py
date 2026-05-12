from skills.registry import register
from skills.llm_docstring_judge import judge_docstrings_batch, is_llm_available

# 占位符关键词（小写）
PLACEHOLDER_KEYWORDS = {"todo", "fixme", "test", "temp", "none", "n/a", "tbd", "placeholder"}

# docstring 最短长度（去空白后）
DOCSTRING_MIN_LEN = 5

# 边界样本判定：长度在此范围内且未命中明显规则，交给 LLM 判断
BORDER_MIN_LEN = 10
BORDER_MAX_LEN = 60
# 样本总数低于此值时跳过 LLM 判断，纯规则处理（避免小数据集串行 API 调用过慢）
LLM_MIN_SAMPLE_COUNT = 20
# 单次送入 LLM 的 border samples 上限；超出部分走规则 fallback（保留）
MAX_LLM_BORDER = 300


def _is_empty_or_whitespace(text) -> bool:
    if text is None:
        return True
    if not isinstance(text, str):
        return True
    return len(text.strip()) == 0


def _is_placeholder(docstring: str) -> bool:
    text = docstring.strip().lower()
    return text in PLACEHOLDER_KEYWORDS


def _is_repetitive_with_function_name(docstring: str, function_name: str) -> bool:
    if not function_name:
        return False

    doc_lower = docstring.strip().lower()
    func_lower = function_name.strip().lower()

    if doc_lower == func_lower:
        return True

    if doc_lower in (f"{func_lower} function", f"{func_lower} method",
                     f"{func_lower}function", f"{func_lower}method"):
        return True

    doc_no_underscore = doc_lower.replace("_", "")
    func_no_underscore = func_lower.replace("_", "")
    if doc_no_underscore == func_no_underscore:
        return True

    return False


def _check_low_quality_reason(sample: dict, doc_field: str, docstring_min_len: int = DOCSTRING_MIN_LEN) -> str | None:
    """规则判断，返回过滤原因；None 表示规则认为合格（可能仍需 LLM 判断）"""
    docstring = sample.get(doc_field)

    if _is_empty_or_whitespace(docstring):
        return "empty_docstring"

    docstring = str(docstring)
    stripped = docstring.strip()

    if len(stripped) < docstring_min_len:
        return "short_docstring"

    if _is_placeholder(stripped):
        return "placeholder_docstring"

    function_name = sample.get("functionName", "")
    if function_name and _is_repetitive_with_function_name(stripped, function_name):
        return "repetitive_docstring"

    return None


def _is_border_sample(sample: dict, doc_field: str) -> bool:
    """
    判断是否为规则难以确定的边界样本，需要交给 LLM 判断。
    条件：规则通过 + docstring 长度在边界区间内（较短，信息量存疑）
    """
    docstring = sample.get(doc_field, "")
    if not isinstance(docstring, str):
        return False
    stripped = docstring.strip()
    return BORDER_MIN_LEN <= len(stripped) <= BORDER_MAX_LEN


@register("filter_low_quality_docstring")
def filter_low_quality_docstring(context: dict) -> dict:
    """过滤低质量 docstring 样本。规则优先，LLM 可选判断边界样本。"""
    samples: list[dict] = context.get("samples", [])
    schema: dict = context.get("schema", {})
    options: dict = context.get("options", {})
    doc_field = schema.get("docstringField")

    # 支持通过 filterRelax 动态调整阈值
    docstring_min_len = int(options.get("docstringMinLen", DOCSTRING_MIN_LEN))

    if not samples or not doc_field:
        n = len(samples)
        return {
            "samples": samples,
            "inputCount": n,
            "outputCount": n,
            "removedCount": 0,
            "emptyDocstringCount": 0,
            "shortDocstringCount": 0,
            "placeholderDocstringCount": 0,
            "repetitiveDocstringCount": 0,
            "llmJudgedCount": 0,
            "llmRemovedCount": 0,
            "status": "success",
            "message": "无需过滤（docstring 字段未配置）",
        }

    input_count = len(samples)
    use_llm = is_llm_available() and input_count >= LLM_MIN_SAMPLE_COUNT

    # 第一层：规则过滤，同时收集边界样本索引
    stats = {
        "empty_docstring": 0,
        "short_docstring": 0,
        "placeholder_docstring": 0,
        "repetitive_docstring": 0,
    }
    rule_passed: list[tuple[int, dict]] = []  # (原始索引, sample)

    for idx, sample in enumerate(samples):
        reason = _check_low_quality_reason(sample, doc_field, docstring_min_len)
        if reason:
            stats[reason] += 1
        else:
            rule_passed.append((idx, sample))

    # 第二层：批量 LLM 判断边界样本
    llm_judged = 0
    llm_removed = 0
    llm_uncertain = 0
    llm_remove_set: set[int] = set()
    llm_failed = False
    llm_error_reason: str | None = None
    border_total = 0
    border_sent_to_llm = 0
    border_fallback_count = 0

    if use_llm:
        border_items = []
        for idx, sample in rule_passed:
            if _is_border_sample(sample, doc_field):
                border_items.append({
                    "id": idx,
                    "docstring": str(sample.get(doc_field, "")).strip(),
                    "function_name": sample.get("functionName", ""),
                })

        border_total = len(border_items)

        # 超出 MAX_LLM_BORDER 的部分走规则 fallback（保留，不丢弃）
        llm_batch = border_items[:MAX_LLM_BORDER]
        fallback_batch = border_items[MAX_LLM_BORDER:]
        border_sent_to_llm = len(llm_batch)
        border_fallback_count = len(fallback_batch)

        if llm_batch:
            verdicts, llm_error_reason = judge_docstrings_batch(llm_batch)
            if llm_error_reason:
                # LLM 失败：所有 border samples 保留（规则已通过，保守处理）
                llm_failed = True
                print(f"[WARN] filter_low_quality_docstring: LLM 判断失败，{border_sent_to_llm} 条 border samples 全部保留。原因: {llm_error_reason}")
            else:
                llm_judged = len(llm_batch)
                for item in llm_batch:
                    verdict = verdicts.get(item["id"], "uncertain")
                    if verdict == "low_quality":
                        llm_removed += 1
                        llm_remove_set.add(item["id"])
                    elif verdict == "uncertain":
                        llm_uncertain += 1

    valid_samples = [
        sample for idx, sample in rule_passed
        if idx not in llm_remove_set
    ]

    output_count = len(valid_samples)
    removed_count = input_count - output_count

    print(f"\n[DEBUG] filter_low_quality_docstring:")
    print(f"  输入样本: {input_count}")
    print(f"  输出样本: {output_count}")
    print(f"  规则过滤: {removed_count - llm_removed}")
    if use_llm:
        print(f"  border samples 总数: {border_total}")
        print(f"  实际送入 LLM: {border_sent_to_llm}")
        print(f"  超出上限 fallback（保留）: {border_fallback_count}")
        if llm_failed:
            print(f"  LLM 状态: 失败/超时，原因: {llm_error_reason}")
            print(f"  LLM fallback: {border_sent_to_llm} 条 border samples 全部保留")
        else:
            print(f"  LLM 判断: {llm_judged} 条")
            print(f"    low_quality: {llm_removed}")
            print(f"    uncertain（保留）: {llm_uncertain}")
            print(f"    high_quality: {llm_judged - llm_removed - llm_uncertain}")
    else:
        print(f"  LLM: 未启用，纯规则模式")
    print(f"  过滤原因统计:")
    for reason, count in stats.items():
        if count > 0:
            print(f"    {reason}: {count}")
    print()

    llm_status_msg = ""
    if use_llm:
        if llm_failed:
            llm_status_msg = f"（LLM 失败/超时，{border_sent_to_llm} 条 border samples 已 fallback 保留）"
        elif llm_judged > 0:
            llm_status_msg = f"（LLM 判断 {llm_judged} 条，fallback {border_fallback_count} 条）"

    return {
        "samples": valid_samples,
        "inputCount": input_count,
        "outputCount": output_count,
        "removedCount": removed_count,
        "emptyDocstringCount": stats["empty_docstring"],
        "shortDocstringCount": stats["short_docstring"],
        "placeholderDocstringCount": stats["placeholder_docstring"],
        "repetitiveDocstringCount": stats["repetitive_docstring"],
        "llmJudgedCount": llm_judged,
        "llmRemovedCount": llm_removed,
        "llmBorderTotal": border_total,
        "llmBorderSent": border_sent_to_llm,
        "llmBorderFallback": border_fallback_count,
        "llmFailed": llm_failed,
        "llmErrorReason": llm_error_reason,
        "lowQualityDocstringCount": removed_count,
        "status": "success",
        "message": f"低质量 docstring 过滤完成，保留 {output_count}/{input_count} 条" + llm_status_msg,
    }
