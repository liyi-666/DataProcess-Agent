"""
LLM 执行方案推荐模块
仅用于 /agent/plan 的推荐生成，不直接控制执行链路
"""
import os
import json
from typing import Optional

ENABLE_LLM_CHAT = os.getenv("ENABLE_LLM_CHAT", "false").lower() == "true"
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "gpt-4")

# 全量 skill 列表（固定顺序，不可增减）
_ALL_SKILLS = [
    "load_dataset",
    "normalize_code_text",
    "extract_function_structure",
    "filter_invalid_samples",
    "filter_low_quality_docstring",
    "deduplicate_samples",
    "rename_variables_augmentation",
    "build_instruction_pairs",
    "compute_dataset_profile",
    "evaluate_data_quality",
    "generate_chart_specs",
]

# 可选 skill（可根据 options 开关控制）
_OPTIONAL_SKILLS = {
    "rename_variables_augmentation": "enableAugmentation",
    "build_instruction_pairs": "enableInstructionPairs",
}

_SYSTEM_PROMPT = """你是一个代码数据集预处理方案规划专家。根据用户的任务说明和数据集情况，推荐合适的处理选项和执行计划。

你只能推荐，不能直接执行。用户可以接受或修改你的推荐。

可选处理选项说明：
- enableDedup: 精确去重（基于代码文本哈希），适合数据来源混杂时
- enableAstDedup: AST 结构去重，识别格式不同但结构相同的代码，计算开销较大
- enableAstExtract: AST 函数结构抽取，提取函数名/参数/返回注解，是高质量训练数据的基础
- enableAugmentation: 变量重命名增强，扩充数据量，适合数据量不足时
- enableInstructionPairs: 构造 docstring->code 等指令样本对，适合用于指令微调

可选 skill 列表（固定顺序，只能选择是否包含，不能改变顺序）：
load_dataset, normalize_code_text, extract_function_structure, filter_invalid_samples,
filter_low_quality_docstring, deduplicate_samples, rename_variables_augmentation,
build_instruction_pairs, compute_dataset_profile, evaluate_data_quality, generate_chart_specs

约束：
1. load_dataset / normalize_code_text / extract_function_structure / filter_invalid_samples /
   filter_low_quality_docstring / deduplicate_samples / compute_dataset_profile /
   evaluate_data_quality / generate_chart_specs 这些 skill 必须始终包含，不可移除
2. rename_variables_augmentation 仅在 enableAugmentation=true 时包含
3. build_instruction_pairs 仅在 enableInstructionPairs=true 时包含
4. 不要推断超出上下文的信息，不要编造数据

返回严格的 JSON 格式，不要输出任何其他内容：
{
  "recommendedOptions": {
    "enableDedup": true或false,
    "enableAstDedup": true或false,
    "enableAstExtract": true或false,
    "enableAugmentation": true或false,
    "enableInstructionPairs": true或false
  },
  "recommendedExecutionPlan": ["skill名称列表"],
  "recommendationReason": "推荐理由，不超过100字"
}"""


def llm_recommend_plan(
    task_description: str,
    detected_schema: dict,
    file_type: str,
    source_granularity: str,
    dataset_observations: dict = None,
) -> Optional[dict]:
    """
    调用 LLM 生成推荐执行方案

    Returns:
        {recommendedOptions, recommendedExecutionPlan, recommendationReason}
        调用失败时返回 None，由调用方使用规则 fallback
    """
    if not ENABLE_LLM_CHAT or not LLM_API_KEY:
        return None

    try:
        from openai import OpenAI

        client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)

        has_docstring = bool(detected_schema.get("docstringField"))
        has_language = bool(detected_schema.get("languageField"))

        obs = dataset_observations or {}
        obs_lines = []
        if obs.get("sampleCount"):
            obs_lines.append(f"- 采样数量：{obs['sampleCount']} 条")
        doc_cov = obs.get("docstringCoverageEstimate")
        if doc_cov is not None:
            obs_lines.append(f"- docstring 覆盖率估计：{int(doc_cov * 100)}%")
        avg_len = obs.get("avgCodeLength", 0)
        if avg_len:
            obs_lines.append(f"- 代码字段平均长度：{avg_len} 字符")
        langs = obs.get("detectedLanguages", [])
        if langs:
            obs_lines.append(f"- 检测到编程语言：{', '.join(langs)}")
        if obs.get("codeFieldLooksLikeFunctions") is not None:
            obs_lines.append(f"- 代码含函数定义：{'是' if obs['codeFieldLooksLikeFunctions'] else '否'}")

        user_prompt = f"""任务说明：{task_description or '（未提供）'}

数据集情况：
- 文件类型：{file_type}
- 数据粒度：{source_granularity}
- 检测到 code 字段：{detected_schema.get('codeField', '未知')}
- 检测到 docstring 字段：{'是' if has_docstring else '否'}
- 检测到 language 字段：{'是' if has_language else '否'}
{chr(10).join(obs_lines) if obs_lines else ''}
请推荐合适的处理选项和执行计划。"""

        response = client.chat.completions.create(
            model=LLM_MODEL_NAME,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=300,
        )

        raw = response.choices[0].message.content.strip()
        parsed = json.loads(raw)

        # 校验结构
        if not all(k in parsed for k in ("recommendedOptions", "recommendedExecutionPlan", "recommendationReason")):
            return None

        opts = parsed["recommendedOptions"]
        plan = parsed["recommendedExecutionPlan"]

        # 校验 plan 中的 skill 名称合法
        valid_skills = set(_ALL_SKILLS)
        plan = [s for s in plan if s in valid_skills]

        # 强制保证必选 skill 存在且顺序正确
        final_plan = _build_validated_plan(opts)
        parsed["recommendedExecutionPlan"] = final_plan

        print(f"[INFO] LLM plan advisor: {parsed.get('recommendationReason', '')}")
        return parsed

    except Exception as e:
        print(f"[WARN] LLM plan advisor failed: {e}")
        return None


def _build_validated_plan(options: dict) -> list[str]:
    """根据 options 构建合法的 executionPlan（保证顺序和必选项）"""
    plan = list(_ALL_SKILLS)
    if not options.get("enableAugmentation", False):
        plan = [s for s in plan if s != "rename_variables_augmentation"]
    if not options.get("enableInstructionPairs", True):
        plan = [s for s in plan if s != "build_instruction_pairs"]
    return plan


def rule_recommend_plan(
    task_description: str,
    detected_schema: dict,
    options_from_request: dict,
    dataset_observations: dict = None,
) -> dict:
    """
    规则 fallback：根据 schema 和请求 options 生成推荐方案
    当 LLM 不可用或调用失败时使用
    """
    has_docstring = bool(detected_schema.get("docstringField"))
    obs = dataset_observations or {}
    doc_coverage = obs.get("docstringCoverageEstimate")
    sample_count = obs.get("sampleCount", 0)

    # 大样本阈值：超过 5 万条时关闭高成本可选步骤
    is_large_dataset = sample_count > 50000

    enable_dedup = options_from_request.get("enableDedup", True)
    enable_ast_dedup = options_from_request.get("enableAstDedup", True)
    enable_ast_extract = options_from_request.get("enableAstExtract", True)
    # 大样本时默认关闭变量重命名增强（逐样本 AST 改写，开销极大）
    enable_augmentation = options_from_request.get("enableAugmentation", False)
    if is_large_dataset:
        enable_augmentation = False
        enable_ast_dedup = False
    # 没有 docstring 字段，或覆盖率极低时，instruction pairs 意义不大
    enable_instruction_pairs = (
        options_from_request.get("enableInstructionPairs", True)
        and has_docstring
        and (doc_coverage is None or doc_coverage >= 0.1)
    )

    recommended_options = {
        "enableDedup": enable_dedup,
        "enableAstDedup": enable_ast_dedup,
        "enableAstExtract": enable_ast_extract,
        "enableAugmentation": enable_augmentation,
        "enableInstructionPairs": enable_instruction_pairs,
    }

    plan = _build_validated_plan(recommended_options)

    reason = "基于规则推荐"
    if is_large_dataset:
        reason += f"；数据集较大（约 {sample_count} 条），已禁用变量重命名增强和 AST 结构去重以控制耗时"
    if not has_docstring:
        reason += "；未检测到 docstring 字段，已禁用 instruction pairs"
    elif doc_coverage is not None and doc_coverage < 0.1:
        reason += f"；docstring 覆盖率仅 {int(doc_coverage * 100)}%，已禁用 instruction pairs"

    return {
        "recommendedOptions": recommended_options,
        "recommendedExecutionPlan": plan,
        "recommendationReason": reason,
    }


def is_llm_available() -> bool:
    return ENABLE_LLM_CHAT and bool(LLM_API_KEY)
