"""
弱化版 Reflection 模块
基于真实 metrics 和 executionLogs 做质量审视，输出警告和建议
不触发重新执行，只做"审视与建议"
"""
import os
import json
from typing import Optional

ENABLE_LLM_CHAT = os.getenv("ENABLE_LLM_CHAT", "false").lower() == "true"
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "gpt-4")

# 规则阈值
_RETAIN_RATE_WARN = 0.5       # 保留率低于此值告警
_SYNTAX_PASS_WARN = 0.7       # 语法通过率低于此值告警
_DOC_COVERAGE_WARN = 0.3      # docstring 覆盖率低于此值告警
_DEDUP_RATIO_WARN = 0.4       # 去重比例（dedupRemoved/raw）高于此值告警
_AUG_SUCCESS_WARN = 0.5       # 增强成功率低于此值告警
_PAIR_PER_SAMPLE_WARN = 0.5   # instruction pairs 每样本不足此值告警

_SYSTEM_PROMPT = """你是一个代码数据集质量审视专家。根据处理结果的指标和执行日志，给出简洁的质量审视和改进建议。

要求：
1. 只基于提供的数据进行分析，不要编造信息
2. 指出最主要的 1-3 个质量瓶颈
3. 给出具体可操作的建议
4. 不要建议重新执行或修改代码
5. 语言简洁，每条建议不超过 40 字

返回严格的 JSON 格式，不要输出任何其他内容：
{
  "reflectionSummary": "一句话总体评价（不超过60字）",
  "qualityWarnings": ["警告1", "警告2"],
  "nextStepSuggestions": ["建议1", "建议2"]
}"""


def _rule_reflect(metrics: dict, execution_logs: list, options: dict) -> dict:
    """规则 reflection：基于阈值生成警告和建议"""
    warnings = []
    suggestions = []

    raw = metrics.get("rawSampleCount", 0)
    final = metrics.get("finalSampleCount", 0)
    retain_rate = metrics.get("retainRate", 0.0)
    syntax_pass = metrics.get("syntaxPassRate", 0.0)
    doc_coverage = metrics.get("docstringCoverage", 0.0)
    ast_failed = metrics.get("astParseFailedCount", 0)
    dedup_removed = metrics.get("dedupRemovedCount", 0)
    aug_success = metrics.get("augmentationSuccessCount", 0)
    aug_failed = metrics.get("augmentationFailedCount", 0)
    pair_count = metrics.get("instructionPairCount", 0)

    # 保留率
    if raw > 0 and retain_rate < _RETAIN_RATE_WARN:
        warnings.append(f"保留率仅 {retain_rate:.1%}，超过一半样本被过滤")
        suggestions.append("检查数据源质量，或适当放宽过滤阈值")

    # 语法通过率
    if raw > 0 and syntax_pass < _SYNTAX_PASS_WARN:
        warnings.append(f"语法通过率 {syntax_pass:.1%}，AST 解析失败较多（{ast_failed} 条）")
        suggestions.append("确认 code 字段是否包含完整函数定义，而非代码片段")

    # docstring 覆盖率
    if raw > 0 and doc_coverage < _DOC_COVERAGE_WARN:
        warnings.append(f"docstring 覆盖率仅 {doc_coverage:.1%}，大量样本缺少文档")
        suggestions.append("考虑补充 docstring 或降低对 docstring 的依赖")

    # 去重比例过高
    if raw > 0 and dedup_removed / raw > _DEDUP_RATIO_WARN:
        ratio = dedup_removed / raw
        warnings.append(f"去重删除比例 {ratio:.1%}（{dedup_removed} 条），数据重复度较高")
        suggestions.append("检查数据来源是否存在大量重复，考虑在采集阶段去重")

    # 增强成功率
    if aug_success + aug_failed > 0:
        aug_rate = aug_success / (aug_success + aug_failed)
        if aug_rate < _AUG_SUCCESS_WARN:
            warnings.append(f"变量重命名增强成功率仅 {aug_rate:.1%}，增强效果有限")
            suggestions.append("增强失败通常因 AST 解析失败，提升语法通过率可改善增强效果")

    # instruction pairs 效果
    if options.get("enableInstructionPairs") and final > 0:
        pair_per_sample = pair_count / final if final > 0 else 0
        if pair_count == 0:
            warnings.append("instruction pairs 构造数量为 0，未生成任何指令样本")
            suggestions.append("确认 docstring 字段是否正确配置，且样本通过了 AST 解析")
        elif pair_per_sample < _PAIR_PER_SAMPLE_WARN:
            warnings.append(f"instruction pairs 平均每样本仅 {pair_per_sample:.2f} 条，构造效果不足")
            suggestions.append("提升 docstring 覆盖率可增加 docstring->code 样本对数量")

    # 整体评价
    if not warnings:
        summary = f"数据质量良好，保留 {final}/{raw} 条样本（{retain_rate:.1%}），未发现明显问题。"
    elif len(warnings) == 1:
        summary = f"数据处理完成，保留 {final}/{raw} 条（{retain_rate:.1%}），存在 1 项需关注的问题。"
    else:
        summary = f"数据处理完成，保留 {final}/{raw} 条（{retain_rate:.1%}），存在 {len(warnings)} 项质量问题需关注。"

    return {
        "reflectionSummary": summary,
        "qualityWarnings": warnings,
        "nextStepSuggestions": suggestions,
    }


def _llm_reflect(metrics: dict, execution_logs: list, summary: str, options: dict) -> Optional[dict]:
    """LLM reflection：生成更自然的质量审视"""
    if not ENABLE_LLM_CHAT or not LLM_API_KEY:
        return None

    try:
        from openai import OpenAI

        client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)

        context = {
            "summary": summary,
            "metrics": metrics,
            "executionLogs": execution_logs,
            "options": options,
        }

        user_prompt = f"""以下是数据预处理任务的执行结果，请进行质量审视：

{json.dumps(context, ensure_ascii=False, indent=2)}"""

        response = client.chat.completions.create(
            model=LLM_MODEL_NAME,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=400,
        )

        raw = response.choices[0].message.content.strip()
        parsed = json.loads(raw)

        required = {"reflectionSummary", "qualityWarnings", "nextStepSuggestions"}
        if not required.issubset(parsed.keys()):
            return None

        return parsed

    except Exception as e:
        print(f"[WARN] LLM reflection failed: {e}")
        return None


def run_reflection(metrics: dict, execution_logs: list, summary: str, options: dict) -> dict:
    """
    执行 reflection：优先 LLM，fallback 到规则

    Returns:
        {reflectionSummary, qualityWarnings, nextStepSuggestions}
    """
    llm_result = _llm_reflect(metrics, execution_logs, summary, options)
    if llm_result:
        print(f"[INFO] reflection: LLM 模式，warnings={len(llm_result.get('qualityWarnings', []))}")
        return llm_result

    rule_result = _rule_reflect(metrics, execution_logs, options)
    print(f"[INFO] reflection: 规则模式，warnings={len(rule_result.get('qualityWarnings', []))}")
    return rule_result
