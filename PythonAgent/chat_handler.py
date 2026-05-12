"""
聊天解释逻辑：支持 LLM 增强 + 规则化 fallback
基于真实 metrics 和 executionLogs 回答用户问题
"""
import os
import json
from typing import Optional

from httpx import stream

# LLM 配置
ENABLE_LLM_CHAT = os.getenv("ENABLE_LLM_CHAT", "false").lower() == "true"
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "deepseek-chat")


def _call_llm(message: str, metrics: dict, execution_logs: list, summary: str) -> Optional[str]:
    """
    调用 LLM 生成自然语言解释

    Args:
        message: 用户问题
        metrics: 任务指标字典
        execution_logs: 执行日志列表
        summary: 任务摘要

    Returns:
        LLM 回复文本，失败时返回 None
    """
    if not ENABLE_LLM_CHAT:
        return None

    if not LLM_API_KEY:
        print("[WARN] LLM_API_KEY not configured, falling back to rule-based chat")
        return None

    try:
        from openai import OpenAI

        client = OpenAI(
            api_key=LLM_API_KEY,
            base_url=LLM_BASE_URL,
        )

        # 构造上下文
        context = {
            "summary": summary,
            "metrics": metrics,
            "executionLogs": execution_logs,
        }

        # 构造 prompt
        system_prompt = """你是一个数据预处理任务的分析助手。用户会向你提问关于数据处理结果的问题。

你必须严格基于提供的上下文数据回答问题，不要编造或推测任何信息。

上下文数据包括：
1. summary: 任务执行摘要
2. metrics: 详细的统计指标（样本数、保留率、语法通过率、docstring 覆盖率等）
3. executionLogs: 每个处理步骤的执行日志（输入数量、输出数量、删除数量、耗时等）

回答要求：
- 只使用上下文中的真实数据
- 如果上下文中没有相关信息，明确告知用户
- 用简洁、专业的语言回答
- 必要时引用具体的指标数值
- 不要添加不确定的推测或建议"""

        user_prompt = f"""用户问题：{message}

上下文数据：
{json.dumps(context, ensure_ascii=False, indent=2)}

请基于上述数据回答用户问题。"""

        response = client.chat.completions.create(
            model=LLM_MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=800,
        )

        reply = response.choices[0].message.content.strip()
        return reply

    except Exception as e:
        print(f"[ERROR] LLM call failed: {e}")
        return None


def _match_keywords(message: str, keywords: list[str]) -> bool:
    """检查 message 是否包含任意关键词"""
    msg_lower = message.lower()
    return any(kw in msg_lower for kw in keywords)


def _explain_filter_reasons(metrics: dict) -> tuple[str, dict]:
    """解释过滤原因"""
    empty_code = metrics.get("emptyCodeCount", 0)
    ast_failed = metrics.get("astParseFailedCount", 0)
    missing_func = metrics.get("missingFunctionNameCount", 0)
    code_short = metrics.get("codeTooShortCount", 0)
    code_long = metrics.get("codeTooLongCount", 0)
    doc_long = metrics.get("docstringTooLongCount", 0)
    low_quality_doc = metrics.get("lowQualityDocstringCount", 0)
    dedup_removed = metrics.get("dedupRemovedCount", 0)

    reasons = []
    refer = {}

    if ast_failed > 0:
        reasons.append(f"AST 解析失败 {ast_failed} 条（语法错误或非完整函数定义）")
        refer["astParseFailedCount"] = ast_failed

    if low_quality_doc > 0:
        reasons.append(f"低质量 docstring 过滤 {low_quality_doc} 条（空、过短、占位或重复）")
        refer["lowQualityDocstringCount"] = low_quality_doc

    if dedup_removed > 0:
        reasons.append(f"去重删除 {dedup_removed} 条（精确去重或 AST 去重）")
        refer["dedupRemovedCount"] = dedup_removed

    if empty_code > 0:
        reasons.append(f"空代码过滤 {empty_code} 条")
        refer["emptyCodeCount"] = empty_code

    if missing_func > 0:
        reasons.append(f"缺失函数名 {missing_func} 条")
        refer["missingFunctionNameCount"] = missing_func

    if code_short > 0:
        reasons.append(f"代码过短 {code_short} 条")
        refer["codeTooShortCount"] = code_short

    if code_long > 0:
        reasons.append(f"代码过长 {code_long} 条")
        refer["codeTooLongCount"] = code_long

    if doc_long > 0:
        reasons.append(f"docstring 过长 {doc_long} 条")
        refer["docstringTooLongCount"] = doc_long

    if not reasons:
        return "当前未发现明显的过滤原因，数据质量较好。", {}

    reply = "过滤原因如下：\n" + "\n".join(f"- {r}" for r in reasons)
    return reply, refer


def _explain_ast_parse(metrics: dict) -> tuple[str, dict]:
    """解释 AST 解析情况"""
    success = metrics.get("astParseSuccessCount", 0)
    failed = metrics.get("astParseFailedCount", 0)
    total = success + failed

    if total == 0:
        return "当前无 AST 解析统计数据。", {}

    syntax_pass_rate = metrics.get("syntaxPassRate", 0.0)

    reply = (
        f"AST 解析统计：\n"
        f"- 解析成功：{success} 条\n"
        f"- 解析失败：{failed} 条\n"
        f"- 语法通过率：{syntax_pass_rate:.2%}\n\n"
        f"解析失败主要可能来自：语法错误、非完整函数定义或字段识别错误。"
        f"建议查看 badcases.json 中的失败样本。"
    )

    refer = {
        "astParseSuccessCount": success,
        "astParseFailedCount": failed,
        "syntaxPassRate": syntax_pass_rate,
    }

    return reply, refer


def _explain_dedup(metrics: dict) -> tuple[str, dict]:
    """解释去重情况"""
    total_removed = metrics.get("dedupRemovedCount", 0)
    exact_removed = metrics.get("exactDedupRemovedCount", 0)
    ast_removed = metrics.get("astDedupRemovedCount", 0)

    if total_removed == 0:
        return "当前未进行去重或无重复样本。", {}

    reply = (
        f"去重统计：\n"
        f"- 总去重数：{total_removed} 条\n"
        f"- 精确去重（基于代码文本哈希）：{exact_removed} 条\n"
        f"- AST 去重（基于 AST 结构哈希）：{ast_removed} 条\n\n"
        f"AST 去重可以识别格式不同但结构相同的代码。"
    )

    refer = {
        "dedupRemovedCount": total_removed,
        "exactDedupRemovedCount": exact_removed,
        "astDedupRemovedCount": ast_removed,
    }

    return reply, refer


def _explain_retain_rate(metrics: dict) -> tuple[str, dict]:
    """解释保留率"""
    raw = metrics.get("rawSampleCount", 0)
    final = metrics.get("finalSampleCount", 0)
    retain_rate = metrics.get("retainRate", 0.0)

    if raw == 0:
        return "当前无样本统计数据。", {}

    reply = (
        f"样本保留情况：\n"
        f"- 原始样本：{raw} 条\n"
        f"- 最终样本：{final} 条\n"
        f"- 保留率：{retain_rate:.2%}\n\n"
    )

    if retain_rate >= 0.8:
        reply += "保留率较高，数据质量良好。"
    elif retain_rate >= 0.6:
        reply += "保留率中等，建议检查过滤原因。"
    else:
        reply += "保留率较低，建议重点关注 AST 解析失败和低质量 docstring 过滤情况。"

    refer = {
        "rawSampleCount": raw,
        "finalSampleCount": final,
        "retainRate": retain_rate,
    }

    return reply, refer


def _explain_quality(metrics: dict) -> tuple[str, dict]:
    """解释数据质量概况"""
    retain_rate = metrics.get("retainRate", 0.0)
    syntax_pass_rate = metrics.get("syntaxPassRate", 0.0)
    doc_coverage = metrics.get("docstringCoverage", 0.0)
    func_match_rate = metrics.get("functionNameMatchRate", 0.0)
    return_anno_rate = metrics.get("returnAnnotationRate", 0.0)

    reply = (
        f"数据质量概况：\n"
        f"- 保留率：{retain_rate:.2%}\n"
        f"- 语法通过率：{syntax_pass_rate:.2%}\n"
        f"- docstring 覆盖率：{doc_coverage:.2%}\n"
        f"- 函数名匹配率：{func_match_rate:.2%}\n"
        f"- 返回注解率：{return_anno_rate:.2%}\n\n"
    )

    # 综合评价
    if retain_rate >= 0.8 and syntax_pass_rate >= 0.9 and doc_coverage >= 0.7:
        reply += "整体质量优秀，适合用于模型训练。"
    elif retain_rate >= 0.6 and syntax_pass_rate >= 0.8:
        reply += "整体质量良好，可用于模型训练。"
    elif retain_rate >= 0.4:
        reply += "整体质量中等，建议进一步清洗或补充高质量样本。"
    else:
        reply += "整体质量较低，建议检查数据源或调整过滤策略。"

    refer = {
        "retainRate": retain_rate,
        "syntaxPassRate": syntax_pass_rate,
        "docstringCoverage": doc_coverage,
        "functionNameMatchRate": func_match_rate,
        "returnAnnotationRate": return_anno_rate,
    }

    return reply, refer


def _explain_general(metrics: dict, summary: str) -> tuple[str, dict]:
    """通用解释：返回 summary + 关键指标"""
    raw = metrics.get("rawSampleCount", 0)
    final = metrics.get("finalSampleCount", 0)
    retain_rate = metrics.get("retainRate", 0.0)

    if summary:
        reply = f"{summary}\n\n"
    else:
        reply = "任务执行完成。\n\n"

    reply += (
        f"关键指标：\n"
        f"- 原始样本：{raw} 条\n"
        f"- 最终样本：{final} 条\n"
        f"- 保留率：{retain_rate:.2%}\n"
    )

    refer = {
        "rawSampleCount": raw,
        "finalSampleCount": final,
        "retainRate": retain_rate,
    }

    return reply, refer


def handle_chat(task_id: int, message: str, metrics: dict, execution_logs: list, summary: str) -> tuple[str, dict]:
    """
    聊天解释逻辑：优先使用 LLM，失败时 fallback 到规则化逻辑

    Args:
        task_id: 任务 ID
        message: 用户问题
        metrics: 任务指标字典
        execution_logs: 执行日志列表
        summary: 任务摘要

    Returns:
        (reply, refer_metrics) 元组
    """
    if not metrics:
        return "当前任务无统计数据，无法回答问题。", {}

    # 1. 尝试使用 LLM
    llm_reply = _call_llm(message, metrics, execution_logs, summary)
    if llm_reply:
        # LLM 成功，提取 referMetrics（使用规则化逻辑）
        refer_metrics = _extract_refer_metrics(message, metrics)
        return llm_reply, refer_metrics

    # 2. Fallback 到规则化逻辑
    # 过滤原因相关
    if _match_keywords(message, ["为什么过滤", "过滤掉", "损失", "为什么删除", "为什么丢失"]):
        return _explain_filter_reasons(metrics)

    # AST 解析相关
    if _match_keywords(message, ["ast", "解析失败", "语法错误", "语法通过率"]):
        return _explain_ast_parse(metrics)

    # 去重相关
    if _match_keywords(message, ["去重", "重复", "dedup", "精确去重", "ast去重"]):
        return _explain_dedup(metrics)

    # 保留率相关
    if _match_keywords(message, ["保留率", "最终样本", "剩下多少", "还剩", "保留了多少"]):
        return _explain_retain_rate(metrics)

    # 质量相关
    if _match_keywords(message, ["质量", "适不适合训练", "数据怎么样", "能不能用", "好不好"]):
        return _explain_quality(metrics)

    # 通用解释
    return _explain_general(metrics, summary)


def _extract_refer_metrics(message: str, metrics: dict) -> dict:
    """
    根据用户问题提取相关的 referMetrics
    这是系统生成的，不是 LLM 生成的
    """
    refer = {}

    # 过滤相关
    if _match_keywords(message, ["为什么过滤", "过滤掉", "损失", "为什么删除", "为什么丢失"]):
        for key in ["astParseFailedCount", "lowQualityDocstringCount", "dedupRemovedCount",
                    "emptyCodeCount", "missingFunctionNameCount", "codeTooShortCount",
                    "codeTooLongCount", "docstringTooLongCount"]:
            if key in metrics and metrics[key] > 0:
                refer[key] = metrics[key]

    # AST 相关
    if _match_keywords(message, ["ast", "解析失败", "语法错误", "语法通过率"]):
        for key in ["astParseSuccessCount", "astParseFailedCount", "syntaxPassRate"]:
            if key in metrics:
                refer[key] = metrics[key]

    # 去重相关
    if _match_keywords(message, ["去重", "重复", "dedup"]):
        for key in ["dedupRemovedCount", "exactDedupRemovedCount", "astDedupRemovedCount"]:
            if key in metrics:
                refer[key] = metrics[key]

    # 保留率相关
    if _match_keywords(message, ["保留率", "最终样本", "剩下多少", "还剩", "保留了多少"]):
        for key in ["rawSampleCount", "finalSampleCount", "retainRate"]:
            if key in metrics:
                refer[key] = metrics[key]

    # 质量相关
    if _match_keywords(message, ["质量", "适不适合训练", "数据怎么样", "能不能用", "好不好"]):
        for key in ["retainRate", "syntaxPassRate", "docstringCoverage",
                    "functionNameMatchRate", "returnAnnotationRate"]:
            if key in metrics:
                refer[key] = metrics[key]

    # 如果没有匹配到任何关键词，返回基础指标
    if not refer:
        for key in ["rawSampleCount", "finalSampleCount", "retainRate"]:
            if key in metrics:
                refer[key] = metrics[key]

    return refer
