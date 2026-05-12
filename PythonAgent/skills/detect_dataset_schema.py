import csv
import json
from collections import Counter

from skills.registry import register

_CANDIDATE_CODE = ["code", "original_string", "content", "source", "code_text", "func_code", "function_code", "source_code", "code_snippet"]
_CANDIDATE_DOC  = ["docstring", "description", "comment", "nl", "func_doc", "doc", "documentation"]
_CANDIDATE_LANG = ["language", "lang", "programming_language"]


def _analyze_samples(rows: list[dict], code_field: str, doc_field: str | None, lang_field: str | None) -> dict:
    """对已读取的样本做轻量统计，供上层构建 observedDatasetTraits 和 riskWarnings。"""
    if not rows:
        return {"sampleCount": 0}

    n = len(rows)

    # docstring 覆盖率
    doc_coverage = 0.0
    if doc_field:
        non_empty = sum(1 for r in rows if str(r.get(doc_field, "")).strip())
        doc_coverage = round(non_empty / n, 2)

    # 代码字段平均长度
    avg_code_len = 0
    if code_field:
        lengths = [len(str(r.get(code_field, ""))) for r in rows]
        avg_code_len = int(sum(lengths) / n) if n else 0

    # 语言分布（取前 3）
    detected_langs: list[str] = []
    if lang_field:
        raw_langs = [str(r.get(lang_field, "")).strip().lower() for r in rows if r.get(lang_field)]
        counts = Counter(raw_langs)
        detected_langs = [lang for lang, _ in counts.most_common(3) if lang]

    # 代码样本是否含函数定义（Python def / class）
    code_looks_like_functions = False
    if code_field:
        snippets = [str(r.get(code_field, "")) for r in rows[:20]]
        code_looks_like_functions = any("def " in s or "class " in s for s in snippets)

    # 字段命名是否非标准（code_field 不在标准候选列表中）
    non_standard_fields = bool(code_field) and code_field not in _CANDIDATE_CODE

    return {
        "sampleCount": n,
        "docstringCoverageEstimate": doc_coverage,
        "avgCodeLength": avg_code_len,
        "detectedLanguages": detected_langs,
        "codeFieldLooksLikeFunctions": code_looks_like_functions,
        "nonStandardFields": non_standard_fields,
    }


def _read_sample_rows(file_path: str, file_type: str, n: int = 50) -> list[dict]:
    if file_type == "jsonl":
        rows = []
        with open(file_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
                if len(rows) >= n:
                    break
        return rows

    if file_type == "csv":
        rows = []
        with open(file_path, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(dict(row))
                if len(rows) >= n:
                    break
        return rows

    if file_type == "parquet":
        import pandas as pd
        df = pd.read_parquet(file_path)
        return df.head(n).to_dict(orient="records")

    return []


def _pick_field(columns: set[str], candidates: list[str]) -> list[str]:
    return [c for c in candidates if c in columns]


@register("detect_dataset_schema")
def detect_dataset_schema(context: dict) -> dict:
    file_path: str = context.get("filePath", "")
    file_type: str = context.get("fileType", "").lower()

    try:
        rows = _read_sample_rows(file_path, file_type)
    except Exception as e:
        return {
            "needUserConfirm": False,
            "confirmPayload": None,
            "detectedSchema": {
                "codeField": "",
                "docstringField": None,
                "languageField": None,
                "candidateCodeFields": [],
                "candidateDocstringFields": [],
                "candidateLanguageFields": [],
            },
            "error": f"读取文件失败: {e}",
        }

    if not rows:
        columns = set()
    else:
        columns = set(rows[0].keys())

    candidate_code = _pick_field(columns, _CANDIDATE_CODE)
    candidate_doc  = _pick_field(columns, _CANDIDATE_DOC)
    candidate_lang = _pick_field(columns, _CANDIDATE_LANG)

    # 如果没有匹配到候选字段，返回所有字段供用户选择
    if not candidate_code and columns:
        candidate_code = sorted(list(columns))
    if not candidate_doc and columns:
        candidate_doc = sorted(list(columns))
    if not candidate_lang and columns:
        candidate_lang = sorted(list(columns))

    # 规则能唯一确定 code 字段
    rule_certain = len(candidate_code) == 1

    if rule_certain:
        code_field = candidate_code[0]
        doc_field  = candidate_doc[0]  if candidate_doc  else None
        lang_field = candidate_lang[0] if candidate_lang else None
        need_confirm = False
        print(f"[INFO] detect_dataset_schema: 规则唯一确定 codeField={code_field}")
    else:
        # 规则无法唯一确定，直接转人工确认
        code_field = ""
        doc_field  = candidate_doc[0]  if len(candidate_doc) == 1 else None
        lang_field = candidate_lang[0] if len(candidate_lang) == 1 else None
        need_confirm = True
        print(f"[INFO] detect_dataset_schema: 规则无法唯一确定，转人工确认，候选={candidate_code}")

    # 先确定推荐字段（用于样本分析）
    if rule_certain:
        recommended_code = code_field
        recommended_doc = doc_field
        recommended_lang = lang_field
    else:
        recommended_code = candidate_code[0] if candidate_code else None
        recommended_doc = candidate_doc[0] if candidate_doc else None
        recommended_lang = candidate_lang[0] if candidate_lang else None

    # 用推荐字段做样本内容分析，结果用于丰富 confirmPayload
    analysis_code_field = recommended_code or ""
    analysis_doc_field = recommended_doc
    analysis_lang_field = recommended_lang
    dataset_observations = _analyze_samples(rows, analysis_code_field, analysis_doc_field, analysis_lang_field)

    # 置信度：high=唯一确定；medium=多候选但均来自标准列表；low=无标准候选退化为全字段
    if rule_certain:
        confidence_level = "high"
        why_need_confirm = None
    else:
        candidates_from_standard = bool(candidate_code) and any(c in _CANDIDATE_CODE for c in candidate_code)
        if candidates_from_standard:
            confidence_level = "medium"
            why_need_confirm = (
                f"检测到 {len(candidate_code)} 个标准候选代码字段（{', '.join(candidate_code)}），"
                "字段名均符合规范，规则无法唯一确定，需要人工确认。"
            )
        else:
            confidence_level = "low"
            why_need_confirm = (
                f"未检测到标准代码字段名，从所有 {len(candidate_code)} 个字段中选取候选，"
                "需要人工指定正确的代码字段。"
            )

    # 构建基于样本内容的推荐理由
    def _build_recommendation_reason(obs: dict, rec_code: str | None, rec_doc: str | None) -> str:
        parts = []
        if rec_code:
            code_parts = []
            if obs.get("codeFieldLooksLikeFunctions"):
                code_parts.append("内容包含函数定义关键字（def/class）")
            avg_len = obs.get("avgCodeLength", 0)
            if avg_len > 200:
                code_parts.append(f"平均长度 {avg_len} 字符，符合代码片段特征")
            elif avg_len > 0:
                code_parts.append(f"平均长度 {avg_len} 字符")
            if rec_code in _CANDIDATE_CODE:
                code_parts.append("字段名在标准代码字段候选列表中")
            if code_parts:
                parts.append(f"代码字段推荐 {rec_code}：" + "；".join(code_parts))
            else:
                parts.append(f"代码字段推荐 {rec_code}（按候选列表优先级）")
        if rec_doc:
            doc_coverage = obs.get("docstringCoverageEstimate", 0)
            if doc_coverage > 0.7:
                parts.append(f"文档字段 {rec_doc} 覆盖率 {int(doc_coverage * 100)}%，质量较好")
            elif doc_coverage > 0.3:
                parts.append(f"文档字段 {rec_doc} 覆盖率 {int(doc_coverage * 100)}%")
        langs = obs.get("detectedLanguages", [])
        if langs:
            parts.append(f"检测到编程语言：{', '.join(langs)}")
        return "；".join(parts) + "。" if parts else "按字段名优先级推荐。"

    confirm_payload = None
    if need_confirm:
        rec_reason = _build_recommendation_reason(dataset_observations, recommended_code, recommended_doc)
        if confidence_level == "medium":
            msg = (
                f"检测到 {len(candidate_code)} 个候选代码字段，"
                f"Agent 推荐 {recommended_code}，请确认或调整字段映射。"
            )
        else:
            msg = (
                f"检测到 {len(candidate_code)} 个候选代码字段，"
                "无法自动确定，请手动选择字段映射。"
            )
        confirm_payload = {
            "message": msg,
            "candidateCodeFields": candidate_code,
            "candidateDocstringFields": candidate_doc,
            "candidateLanguageFields": candidate_lang,
            "recommendedCodeField": recommended_code,
            "recommendedDocstringField": recommended_doc,
            "recommendedLanguageField": recommended_lang,
            "recommendationReason": rec_reason,
            "confidenceLevel": confidence_level,
            "whyNeedUserConfirm": why_need_confirm,
        }

    return {
        "needUserConfirm": need_confirm,
        "confirmPayload": confirm_payload,
        "datasetObservations": dataset_observations,
        "detectedSchema": {
            "codeField": code_field,
            "docstringField": doc_field,
            "languageField": lang_field,
            "candidateCodeFields": candidate_code,
            "candidateDocstringFields": candidate_doc,
            "candidateLanguageFields": candidate_lang,
        },
    }
