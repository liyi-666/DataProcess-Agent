"""
LLM docstring 质量判断模块
仅用于 filter_low_quality_docstring 的边界样本判断
"""
import os
import json
from typing import Literal

ENABLE_LLM_CHAT = os.getenv("ENABLE_LLM_CHAT", "false").lower() == "true"
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "gpt-4")

DocstringQuality = Literal["high_quality", "low_quality", "uncertain"]

_SYSTEM_PROMPT = """你是一个代码数据集质量评估专家。你的任务是批量判断多条 Python 函数的 docstring 是否具有有效监督信号，用于代码生成模型训练。

判断标准（必须全部考虑）：
1. docstring 是否明确描述了函数的主要行为（而不是模糊的"处理数据"之类）
2. 是否提供了足够具体的信息，而不是泛泛而谈
3. 是否能帮助模型推断函数的实现方向
4. 是否不是纯占位或模板化描述（如"This function does something"）

你会收到一个 JSON 数组，每项包含 id、docstring 和可选的 function_name。
你只能返回以下 JSON 格式，不要输出任何其他内容：
[{"id": <id>, "result": "high_quality"}, {"id": <id>, "result": "low_quality"}, ...]

result 取值：
- high_quality：docstring 有明确的行为描述，具备有效监督信号
- low_quality：docstring 模糊、无意义或无法帮助推断实现
- uncertain：无法明确判断，存在争议"""


# LLM 单次调用超时（秒）；默认 10s，可通过环境变量覆盖
LLM_TIMEOUT = float(os.getenv("LLM_JUDGE_TIMEOUT", "10"))
# 单次 LLM 调用最大 token 上限（防止超大 payload）
LLM_MAX_TOKENS_PER_ITEM = 50
LLM_MAX_OUTPUT_TOKENS = 4096


class LLMJudgeError(Exception):
    """LLM 判断失败（超时、网络错误、解析失败等）"""


def judge_docstrings_batch(items: list[dict]) -> tuple[dict[int, DocstringQuality], str | None]:
    """
    批量调用 LLM 判断多条 docstring 质量。

    Args:
        items: [{"id": int, "docstring": str, "function_name": str}, ...]

    Returns:
        (results, error_reason)
        results: {id: "high_quality" | "low_quality" | "uncertain"}
        error_reason: None 表示成功；非 None 表示失败原因（调用方可记录 warning）
    """
    fallback = {item["id"]: "uncertain" for item in items}
    if not items or not ENABLE_LLM_CHAT or not LLM_API_KEY:
        return fallback, None

    try:
        from openai import OpenAI

        client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL, timeout=LLM_TIMEOUT)

        payload = [
            {
                "id": item["id"],
                "docstring": item["docstring"].strip(),
                **({"function_name": item["function_name"]} if item.get("function_name") else {}),
            }
            for item in items
        ]

        max_tokens = min(LLM_MAX_TOKENS_PER_ITEM * len(items), LLM_MAX_OUTPUT_TOKENS)

        response = client.chat.completions.create(
            model=LLM_MODEL_NAME,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            temperature=0.0,
            max_tokens=max_tokens,
        )

        raw = response.choices[0].message.content.strip()
        parsed = json.loads(raw)

        results = {}
        for entry in parsed:
            item_id = entry.get("id")
            result = entry.get("result", "uncertain")
            if result not in ("high_quality", "low_quality", "uncertain"):
                result = "uncertain"
            results[item_id] = result

        # 补全未返回的 id
        for item in items:
            if item["id"] not in results:
                results[item["id"]] = "uncertain"

        return results, None

    except Exception as e:
        error_reason = f"{type(e).__name__}: {e}"
        print(f"[WARN] LLM docstring batch judge failed: {error_reason}")
        return fallback, error_reason


def judge_docstring(docstring: str, function_name: str = "") -> DocstringQuality:
    """单条判断，内部复用批量接口"""
    results, _ = judge_docstrings_batch([{"id": 0, "docstring": docstring, "function_name": function_name}])
    return results.get(0, "uncertain")


def is_llm_available() -> bool:
    return ENABLE_LLM_CHAT and bool(LLM_API_KEY)
