"""
LLM 辅助 schema 字段判断模块
仅在规则无法唯一识别字段时调用，不直接决定执行流程
"""
import os
import json
from typing import Optional

ENABLE_LLM_CHAT = os.getenv("ENABLE_LLM_CHAT", "false").lower() == "true"
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "gpt-4")

_SYSTEM_PROMPT = """你是一个数据集字段识别专家。你的任务是根据字段名和样本值，判断哪个字段对应 code、docstring、language 角色。

规则：
1. 只能判断字段角色（code / docstring / language），不能推断超出上下文的信息
2. 不能凭空编造字段含义，只能基于提供的字段名和样本值
3. 置信不足时必须返回 uncertain，不要强行猜测
4. code 字段：包含源代码文本
5. docstring 字段：包含函数说明、注释或文档字符串
6. language 字段：包含编程语言名称（如 python、java、javascript）

你只能返回以下 JSON 格式，不要输出任何其他内容：
{
  "codeField": "字段名或null",
  "docstringField": "字段名或null",
  "languageField": "字段名或null",
  "confidence": "high或low",
  "reason": "简短理由（不超过50字）"
}

confidence 说明：
- high：有明确依据，可以信任
- low：存在歧义或不确定，建议人工确认"""


def llm_judge_schema(
    candidate_columns: list[str],
    sample_rows: list[dict],
    file_type: str,
) -> Optional[dict]:
    """
    调用 LLM 对候选字段做辅助判断

    Args:
        candidate_columns: 所有字段名列表
        sample_rows: 前几条样本数据
        file_type: 文件类型

    Returns:
        {codeField, docstringField, languageField, confidence, reason}
        调用失败或置信不足时返回 None
    """
    if not ENABLE_LLM_CHAT or not LLM_API_KEY:
        return None

    try:
        from openai import OpenAI

        client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)

        # 构造每个字段的样本值预览（最多3条，每条截断到100字符）
        field_previews = {}
        for col in candidate_columns:
            values = []
            for row in sample_rows[:3]:
                val = row.get(col)
                if val is not None:
                    s = str(val).strip().replace("\n", " ")
                    values.append(s[:100] + "..." if len(s) > 100 else s)
            field_previews[col] = values

        user_prompt = f"""文件类型：{file_type}
字段列表：{candidate_columns}

各字段样本值（最多3条）：
{json.dumps(field_previews, ensure_ascii=False, indent=2)}

请判断哪个字段对应 code、docstring、language 角色。"""

        response = client.chat.completions.create(
            model=LLM_MODEL_NAME,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
            max_tokens=150,
        )

        raw = response.choices[0].message.content.strip()
        parsed = json.loads(raw)

        # 校验返回结构
        required_keys = {"codeField", "docstringField", "languageField", "confidence", "reason"}
        if not required_keys.issubset(parsed.keys()):
            return None

        # confidence low 视为不确定，返回 None 触发 WAITING_CONFIRM
        if parsed.get("confidence") == "low":
            print(f"[INFO] LLM schema judge: confidence=low, reason={parsed.get('reason')}")
            return None

        # codeField 必须有值才算有效
        if not parsed.get("codeField"):
            return None

        # 校验 LLM 返回的字段名必须在候选列表中
        col_set = set(candidate_columns)
        for key in ("codeField", "docstringField", "languageField"):
            val = parsed.get(key)
            if val and val not in col_set:
                print(f"[WARN] LLM returned unknown field '{val}' for {key}, ignoring")
                parsed[key] = None

        print(f"[INFO] LLM schema judge: confidence=high, reason={parsed.get('reason')}")
        return parsed

    except Exception as e:
        print(f"[WARN] LLM schema judge failed: {e}")
        return None


def is_llm_available() -> bool:
    return ENABLE_LLM_CHAT and bool(LLM_API_KEY)
