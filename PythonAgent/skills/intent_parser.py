"""
用户意图解析模块：将自然语言优化请求映射为 RefinementAction
Agent 作为策略层中枢：理解意图 → 生成策略方案 → 解释原因 → 请求确认
"""
import os
import json
from models import RefinementAction

ENABLE_LLM_CHAT = os.getenv("ENABLE_LLM_CHAT", "false").lower() == "true"
LLM_API_KEY = os.getenv("LLM_API_KEY", "")

# 白名单：LLM 输出的 optionsDiff / filterRelax 只允许这些 key
_VALID_OPTIONS_KEYS = {"enableDedup", "enableAstDedup", "enableAstExtract", "enableAugmentation", "enableInstructionPairs"}
_VALID_FILTER_RELAX_KEYS = {"docstringMinLen"}
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "gpt-4")

_INTENT_SYSTEM_PROMPT = """你是一个代码数据集预处理 Agent，负责理解用户的优化意图并生成结构化的策略方案。

你的职责：
1. 理解用户表达的高层目标（不是让用户自己调参数）
2. 确定优化目标类型（optimizationGoal）
3. 生成策略理由列表（strategyReason）：解释为什么这样调整
4. 生成预期影响列表（expectedImpact）：告知用户可能的结果
5. 生成风险提示列表（riskWarnings）：告知潜在风险（可为空）
6. 生成完整的 intentSummary：用自然语言复述理解和策略
7. 如果意图不明确，通过 clarificationNeeded 请求用户补充

可调整的选项（optionsDiff 字段）：
- enableDedup (bool): 是否启用哈希去重
- enableAstDedup (bool): 是否启用 AST 结构去重（识别格式不同但逻辑相同的重复代码）
- enableAstExtract (bool): 是否启用 AST 函数结构提取
- enableAugmentation (bool): 是否启用变量重命名数据增强（可扩充样本量约 30-50%，不能指定目标数量）
- enableInstructionPairs (bool): 是否构造指令对（docstring→code 等训练格式）

可放宽的过滤阈值（filterRelax 字段）：
- docstringMinLen (int): docstring 最短长度，默认 5，放宽可保留更多短文档样本

optimizationGoal 取值（选最匹配的一个）：
- maximize_retention: 最大化样本保留率
- maximize_quality: 最大化数据质量/监督信号质量
- balance_retain_and_quality: 平衡保留率与质量
- training_data_construction: 偏向训练数据构造（指令对、增强）
- reduce_noise: 减少噪声/加强去重
- data_augmentation: 数据增强/扩充样本量
- compare_rounds: 对比两轮结果（不重跑）

actionType 取值：
- explain: 用户在提问或请求解释（含"为什么"、"多少"、"什么是"、"怎么"等疑问句），不需要重跑
- rerun_with_options: 调整参数后重新执行（最常见）
- clarify: 需要用户补充说明才能继续
- compare: 用户只是想对比两轮结果，不需要重跑

confidence 取值：high / medium / low

intentSummary 要求：
- 必须是完整句子，体现 Agent 的理解和策略
- 要说明：理解到的用户目标 + 准备做什么改动 + 为什么这么改

strategyReason 要求：
- 列表，每条说明一个具体的策略决策及其原因
- 示例：["关闭 AST 去重可减少结构重复带来的样本损失", "适度放宽 docstring 最短长度可提升保留率"]

expectedImpact 要求：
- 列表，每条描述一个预期的量化或定性影响
- 示例：["预计保留率会上升 10-20%", "instruction pairs 数量可能增加"]

riskWarnings 要求：
- 列表，每条描述一个潜在风险（如果没有风险可为 null 或空列表）
- 示例：["若 docstring 质量本身较弱，放宽过滤可能引入更多低信息量监督信号"]

上下文感知说明：
- 输入中包含 currentMetrics（上一轮指标）、currentOptions（上一轮选项）、reflectionSummary（上一轮反思）、previousRefinementAction（上一轮的修订动作）
- 请结合这些上下文理解用户的相对表达，如"再放宽一点"、"退回去一点"、"保持 X 不变但改 Y"

【重要：系统能力边界】
以下请求超出系统当前能力，必须返回 actionType=clarify，并在 clarificationNeeded 中说明系统实际能做什么：
- 更改输出格式（Alpaca、ShareGPT、JSONL、CSV 等格式转换）：系统只能生成 docstring→code 指令对，不支持特定格式 schema 转换
- 过滤特定编程语言：系统没有语言过滤参数
- 从某一步骤开始重跑（partial rerun）：系统只支持全量重跑
- 合并多个文件：系统每次只处理一个文件
- 分析哪些样本质量最差：系统没有样本级分析接口
- 设置条件中断（如保留率低于 X% 就停止）：系统不支持条件中断
- 调整语法检查严格程度：语法检查阈值未开放
- 扩充到指定数量（如"扩充到 10000 条"、"生成 5000 条"）：系统增强只能按比例扩充约 30-50%，不能控制目标数量
不要把"听起来相关"的功能（如 enableInstructionPairs、enableAugmentation）误用来响应超出能力范围的请求。

只返回以下 JSON 格式，不要输出任何其他内容：
{
  "actionType": "<actionType>",
  "intentSummary": "<完整的 Agent 策略复述>",
  "optimizationGoal": "<optimizationGoal>",
  "strategyReason": ["<原因1>", "<原因2>"],
  "optionsDiff": { <见下方约束> },
  "filterRelax": { <见下方约束> },
  "expectedImpact": ["<影响1>", "<影响2>"],
  "riskWarnings": ["<风险1>"],
  "confidence": "<high|medium|low>",
  "clarificationNeeded": "<需要用户补充的问题或 null>"
}

【严格约束】optionsDiff 只能包含以下 key，其他 key 一律不写：
enableDedup / enableAstDedup / enableAstExtract / enableAugmentation / enableInstructionPairs
value 只能是 true 或 false。

【严格约束】filterRelax 只能包含以下 key，其他 key 一律不写：
docstringMinLen
value 只能是正整数。

如果用户的请求无法通过以上选项实现，必须返回 actionType=clarify，不得在 optionsDiff 或 filterRelax 中发明不存在的 key。"""


# ── 规则解析辅助 ──────────────────────────────────────────────

def _has(msg: str, *keywords: str) -> bool:
    m = msg.lower()
    return any(k in m for k in keywords)


def _rule_parse(message: str, current_options: dict, current_metrics: dict) -> RefinementAction:
    msg = message.lower()

    # ── 优先拦截：疑问句 / 解释类请求 → explain ──
    _EXPLAIN_KEYWORDS = (
        "为什么", "为何", "多少", "什么是", "什么叫", "怎么", "如何",
        "解释", "说明", "原因", "是什么", "有多", "能不能告诉",
        "why", "what is", "what are", "how many", "how much", "how does", "explain",
    )
    if _has(msg, *_EXPLAIN_KEYWORDS):
        return RefinementAction(
            actionType="explain",
            intentSummary="用户在提问，将由 Agent 解释。",
            optimizationGoal=None,
            strategyReason=None,
            optionsDiff={},
            filterRelax=None,
            expectedImpact=None,
            riskWarnings=None,
            confidence="high",
            clarificationNeeded=None,
        )

    # ── 优先拦截：明确超出系统能力的请求 ──
    if _has(msg, "alpaca", "sharegpt", "share_gpt", "jsonl格式", "csv格式", "格式转换", "输出格式"):
        return RefinementAction(
            actionType="clarify",
            intentSummary="您希望更改输出格式，但当前系统不支持 Alpaca/ShareGPT 等特定格式转换。",
            optimizationGoal=None,
            strategyReason=None,
            optionsDiff={},
            filterRelax=None,
            expectedImpact=None,
            riskWarnings=None,
            confidence="high",
            clarificationNeeded=(
                "当前系统不支持将输出转换为 Alpaca 或 ShareGPT 格式。\n"
                "系统目前能做的训练数据构造是：开启指令对（enableInstructionPairs），"
                "生成 docstring→code、signature→body、code→docstring 三种简单对，"
                "但不会输出特定格式的 JSON schema。\n"
                "如果您希望生成指令对格式，我可以帮您开启这个选项。"
            ),
        )

    # 检测"扩充到 N 条"这类带目标数量的请求
    import re
    if re.search(r'(扩充|生成|增加|达到|到达|凑够).{0,6}(\d+)\s*(条|个|样本|数据)', msg) or \
       re.search(r'(\d+)\s*(条|个|样本|数据).{0,6}(扩充|生成|增加)', msg):
        return RefinementAction(
            actionType="clarify",
            intentSummary="您希望将数据扩充到指定数量，但当前系统不支持按目标数量控制增强。",
            optimizationGoal=None,
            strategyReason=None,
            optionsDiff={},
            filterRelax=None,
            expectedImpact=None,
            riskWarnings=None,
            confidence="high",
            clarificationNeeded=(
                "系统的变量重命名增强只能按比例扩充样本量（约 30-50%），无法指定目标数量。\n"
                "如果您希望增加样本量，我可以帮您开启增强选项，但最终数量取决于原始数据规模。"
            ),
        )

    if _has(msg, "partial rerun", "从第", "从步骤", "跳过", "只跑", "checkpoint"):
        return RefinementAction(
            actionType="clarify",
            intentSummary="您希望从某一步骤开始重跑，但当前系统只支持全量重跑。",
            optimizationGoal=None,
            strategyReason=None,
            optionsDiff={},
            filterRelax=None,
            expectedImpact=None,
            riskWarnings=None,
            confidence="high",
            clarificationNeeded="当前系统不支持从指定步骤开始重跑，每次都会从头执行完整流程。您可以调整选项后启动新一轮全量重跑。",
        )

    if _has(msg, "过滤语言", "只保留python", "只保留java", "language filter", "编程语言过滤"):
        return RefinementAction(
            actionType="clarify",
            intentSummary="您希望按编程语言过滤样本，但当前系统没有语言过滤参数。",
            optimizationGoal=None,
            strategyReason=None,
            optionsDiff={},
            filterRelax=None,
            expectedImpact=None,
            riskWarnings=None,
            confidence="high",
            clarificationNeeded="当前系统不支持按编程语言过滤，所有语言的样本都会被处理。",
        )

    opts: dict = {}
    filter_relax: dict = {}
    confidence = "high"
    action_type = "rerun_with_options"
    optimization_goal = None
    strategy_reason: list[str] = []
    expected_impact: list[str] = []
    risk_warnings: list[str] = []
    summary_parts: list[str] = []

    # ── 对比意图（不需要重跑）──
    if _has(msg, "对比", "比较", "compare", "上一轮", "差异"):
        return RefinementAction(
            actionType="compare",
            intentSummary="您希望查看本轮与上一轮的处理结果对比。请点击页面上的【对比上一轮】按钮，系统会展示两轮的 metrics 差异。",
            optimizationGoal="compare_rounds",
            strategyReason=["对比两轮 metrics 可以直观看出参数调整的效果"],
            optionsDiff={},
            filterRelax=None,
            expectedImpact=["展示两轮的 metrics 差异对比表"],
            riskWarnings=None,
            confidence="high",
            clarificationNeeded=None,
        )

    # ── 保留更多样本 / 放宽过滤 ──
    if _has(msg, "更多", "保留", "少过滤", "样本量", "expand", "keep more", "放宽", "宽松"):
        opts["enableAstDedup"] = False
        optimization_goal = "maximize_retention"
        summary_parts.append("您希望保留更多样本")
        strategy_reason.append("关闭 AST 结构去重可减少因格式差异导致的样本损失")
        expected_impact.append("预计样本保留率上升 10-20%")

        if _has(msg, "docstring", "文档", "注释", "短", "简短"):
            filter_relax["docstringMinLen"] = 3
            strategy_reason.append("放宽 docstring 最短长度至 3 个字符，保留更多短文档样本")
            expected_impact.append("更多短 docstring 样本将被保留")
            risk_warnings.append("放宽 docstring 过滤可能引入信息量较少的监督信号")

    # ── 去重 / 减少重复 ──
    if _has(msg, "去重", "重复", "dedup", "duplicate"):
        opts["enableDedup"] = True
        opts["enableAstDedup"] = True
        optimization_goal = optimization_goal or "reduce_noise"
        summary_parts.append("您希望加强去重")
        strategy_reason.append("同时开启精确去重（哈希）和 AST 结构去重，覆盖文本重复和结构重复两种情况")
        expected_impact.append("重复样本将被更彻底地清除，数据集多样性提升")
        risk_warnings.append("加强去重会减少样本总量，保留率可能下降")

    # ── 数据增强 ──
    if _has(msg, "增强", "augment", "变量重命名", "rename", "扩充"):
        opts["enableAugmentation"] = True
        optimization_goal = optimization_goal or "data_augmentation"
        summary_parts.append("您希望扩充数据量")
        strategy_reason.append("开启变量重命名增强，通过系统性重命名函数中的变量名生成语义等价的新样本")
        expected_impact.append("样本量可扩充约 30-50%")
        risk_warnings.append("增强样本与原始样本高度相似，若模型对多样性敏感需注意")

    # ── 指令对 ──
    if _has(msg, "指令对", "instruction", "pair", "训练格式", "sft", "微调"):
        opts["enableInstructionPairs"] = True
        optimization_goal = optimization_goal or "training_data_construction"
        summary_parts.append("您希望生成训练用的指令对格式")
        strategy_reason.append("开启指令对构造，生成 docstring→code、signature→body、code→docstring 三种训练格式")
        expected_impact.append("输出数据集将包含结构化的指令对，适合直接用于 SFT 微调")

    # ── 质量提升 ──
    if _has(msg, "质量", "低质量", "quality", "提升", "更严格", "严格过滤", "监督信号"):
        opts["enableDedup"] = True
        opts["enableAstDedup"] = True
        optimization_goal = optimization_goal or "maximize_quality"
        summary_parts.append("您希望提升数据质量")
        strategy_reason.append("开启全量去重（精确 + AST）以减少重复样本")
        strategy_reason.append("保持严格的 docstring 过滤以确保监督信号质量")
        expected_impact.append("保留样本的质量更高，更适合模型训练")
        risk_warnings.append("严格过滤会减少样本总量，保留率可能明显下降")

    # ── AST 提取 ──
    if _has(msg, "ast", "语法", "解析", "结构提取"):
        opts["enableAstExtract"] = True
        optimization_goal = optimization_goal or "maximize_quality"
        summary_parts.append("您希望启用 AST 函数结构提取")
        strategy_reason.append("AST 提取可解析每个函数的参数、返回注解和 docstring 结构，提升样本的结构化程度")
        expected_impact.append("样本将包含更丰富的结构化元数据")

    # ── 无法识别 ──
    if not opts and not filter_relax:
        return RefinementAction(
            actionType="clarify",
            intentSummary="我需要更多信息才能为您制定合适的处理策略。",
            optimizationGoal=None,
            strategyReason=None,
            optionsDiff={},
            filterRelax=None,
            expectedImpact=None,
            riskWarnings=None,
            confidence="low",
            clarificationNeeded=(
                "我没有完全理解您的优化目标。您是希望：\n"
                "(1) 保留更多样本（放宽过滤）\n"
                "(2) 提升数据质量（加强过滤）\n"
                "(3) 扩充数据量（开启增强）\n"
                "(4) 生成训练格式（指令对）\n"
                "还是其他目标？"
            ),
        )

    intent_summary = "；".join(summary_parts) + "。"
    if strategy_reason:
        intent_summary += "策略：" + "；".join(strategy_reason[:2]) + "。"

    return RefinementAction(
        actionType=action_type,
        intentSummary=intent_summary,
        optimizationGoal=optimization_goal,
        strategyReason=strategy_reason if strategy_reason else None,
        optionsDiff=opts,
        filterRelax=filter_relax if filter_relax else None,
        expectedImpact=expected_impact if expected_impact else None,
        riskWarnings=risk_warnings if risk_warnings else None,
        confidence=confidence,
        clarificationNeeded=None,
    )


# ── LLM 解析 ──────────────────────────────────────────────────

def _llm_parse(
    message: str,
    current_metrics: dict,
    current_options: dict,
    summary: str,
    reflection_summary: str,
    previous_refinement_action: dict | None,
) -> RefinementAction | None:
    if not ENABLE_LLM_CHAT or not LLM_API_KEY:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)

        user_content = {
            "userMessage": message,
            "currentMetrics": current_metrics or {},
            "currentOptions": current_options or {},
            "summary": summary or "",
            "reflectionSummary": reflection_summary or "",
            "previousRefinementAction": previous_refinement_action or {},
        }

        response = client.chat.completions.create(
            model=LLM_MODEL_NAME,
            messages=[
                {"role": "system", "content": _INTENT_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(user_content, ensure_ascii=False)},
            ],
            temperature=0.0,
            max_tokens=800,
        )
        raw = response.choices[0].message.content.strip()
        parsed = json.loads(raw)

        action_type = parsed.get("actionType", "rerun_with_options")
        if action_type not in ("rerun_with_options", "clarify", "compare", "explain"):
            action_type = "rerun_with_options"

        confidence = parsed.get("confidence", "medium")
        if confidence not in ("high", "medium", "low"):
            confidence = "medium"

        # 白名单过滤：丢弃 LLM 幻觉出的非法 key，不透传给执行层
        raw_opts = parsed.get("optionsDiff") or {}
        safe_opts = {k: v for k, v in raw_opts.items() if k in _VALID_OPTIONS_KEYS and isinstance(v, bool)}

        raw_relax = parsed.get("filterRelax") or {}
        safe_relax = {k: v for k, v in raw_relax.items() if k in _VALID_FILTER_RELAX_KEYS and isinstance(v, int) and v > 0}

        # 如果 LLM 幻觉出了非法 key 但 actionType 不是 clarify，降级为 clarify
        illegal_opts = set((parsed.get("optionsDiff") or {}).keys()) - _VALID_OPTIONS_KEYS
        illegal_relax = set((parsed.get("filterRelax") or {}).keys()) - _VALID_FILTER_RELAX_KEYS
        if (illegal_opts or illegal_relax) and action_type != "clarify":
            print(f"[WARN] LLM hallucinated illegal keys: opts={illegal_opts} relax={illegal_relax}, downgrading to clarify")
            return RefinementAction(
                actionType="clarify",
                intentSummary=parsed.get("intentSummary", ""),
                optimizationGoal=parsed.get("optimizationGoal"),
                strategyReason=None,
                optionsDiff={},
                filterRelax=None,
                expectedImpact=None,
                riskWarnings=None,
                confidence="low",
                clarificationNeeded="您的请求超出了当前系统的处理能力范围。系统目前只能调整去重、过滤、增强和指令对构造这几个选项，无法实现其他格式转换或处理方式。",
            )

        return RefinementAction(
            actionType=action_type,
            intentSummary=parsed.get("intentSummary", ""),
            optimizationGoal=parsed.get("optimizationGoal"),
            strategyReason=parsed.get("strategyReason"),
            optionsDiff=safe_opts,
            filterRelax=safe_relax if safe_relax else None,
            expectedImpact=parsed.get("expectedImpact"),
            riskWarnings=parsed.get("riskWarnings"),
            confidence=confidence,
            clarificationNeeded=parsed.get("clarificationNeeded"),
        )
    except Exception as e:
        print(f"[WARN] LLM intent parse failed: {e}")
        return None


# ── 公开入口 ──────────────────────────────────────────────────

def parse_user_intent(
    message: str,
    current_metrics: dict | None = None,
    current_options: dict | None = None,
    summary: str = "",
    reflection_summary: str = "",
    previous_refinement_action: dict | None = None,
) -> RefinementAction:
    llm_result = _llm_parse(
        message,
        current_metrics or {},
        current_options or {},
        summary,
        reflection_summary,
        previous_refinement_action,
    )
    if llm_result is not None:
        return llm_result
    return _rule_parse(message, current_options or {}, current_metrics or {})