import re

from skills.registry import register


def _normalize_code(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\t", "    ")
    return text.strip()


def _normalize_docstring(text: str) -> str:
    text = text.strip()
    # strip outer triple quotes (both """ and ''')
    for q in ('"""', "'''"):
        if text.startswith(q) and text.endswith(q) and len(text) >= len(q) * 2:
            text = text[len(q):-len(q)].strip()
            break
    # collapse consecutive whitespace (spaces/tabs) but preserve newlines
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


@register("normalize_code_text")
def normalize_code_text(context: dict) -> dict:
    samples: list[dict] = context.get("samples", [])
    schema: dict = context.get("schema", {})

    code_field = schema.get("codeField", "")
    doc_field  = schema.get("docstringField")

    if not samples or not code_field:
        n = len(samples)
        return {
            "samples": samples,
            "inputCount": n,
            "outputCount": n,
            "removedCount": 0,
            "status": "success",
            "message": "无需规范化（字段未配置）",
        }

    normalized = []
    for row in samples:
        row = dict(row)
        if code_field in row and row[code_field] is not None:
            row[code_field] = _normalize_code(str(row[code_field]))
        if doc_field and doc_field in row and row[doc_field] is not None:
            row[doc_field] = _normalize_docstring(str(row[doc_field]))
        normalized.append(row)

    # 调试输出：打印前3条规范化后的样本
    print("\n[DEBUG] normalize_code_text 处理结果：")
    for i, sample in enumerate(normalized[:3]):
        print(f"  样本 {i}:")
        print(f"    code: {repr(sample.get(code_field, ''))}")
        if doc_field:
            print(f"    docstring: {repr(sample.get(doc_field, ''))}")
    print()

    n = len(normalized)
    return {
        "samples": normalized,
        "inputCount": n,
        "outputCount": n,
        "removedCount": 0,
        "status": "success",
        "message": f"代码文本规范化完成，共处理 {n} 条",
    }
