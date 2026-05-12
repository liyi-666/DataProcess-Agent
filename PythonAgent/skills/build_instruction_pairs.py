import ast
import json
import os
from pathlib import Path
from typing import Optional

from skills.registry import register


# Instruction 模板
INSTRUCTION_TEMPLATES = {
    "docstring_to_code": "Generate Python function implementation from the given docstring.",
    "signature_to_body": "Complete the Python function body according to the signature.",
    "code_to_docstring": "Generate a concise docstring for the given Python function.",
}


def _extract_signature(sample: dict, code_field: str) -> Optional[str]:
    """提取函数签名"""
    code = sample.get(code_field, "")
    if not code or not isinstance(code, str):
        return None

    try:
        tree = ast.parse(code)
        func_nodes = [node for node in tree.body
                      if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]

        if not func_nodes:
            return None

        func_node = func_nodes[0]

        # 构造签名
        is_async = isinstance(func_node, ast.AsyncFunctionDef)
        prefix = "async def " if is_async else "def "

        # 函数名
        func_name = func_node.name

        # 参数
        args_str = ast.unparse(func_node.args)

        # 返回注解
        returns_str = ""
        if func_node.returns:
            returns_str = f" -> {ast.unparse(func_node.returns)}"

        signature = f"{prefix}{func_name}({args_str}){returns_str}:"

        return signature

    except Exception:
        return None


def _build_docstring_to_code_pair(sample: dict, code_field: str, doc_field: str) -> Optional[dict]:
    """构造 docstring -> code pair"""
    # 检查是否有 docstring
    docstring = sample.get(doc_field) or sample.get("docstringInCode")
    if not docstring or not isinstance(docstring, str) or not docstring.strip():
        return None

    # 检查是否有 code
    code = sample.get(code_field, "")
    if not code or not isinstance(code, str):
        return None

    function_name = sample.get("functionName", "")

    return {
        "pairType": "docstring_to_code",
        "instruction": INSTRUCTION_TEMPLATES["docstring_to_code"],
        "input": docstring.strip(),
        "output": code,
        "sourceFunctionName": function_name,
    }


def _build_signature_to_body_pair(sample: dict, code_field: str) -> Optional[dict]:
    """构造 signature -> body pair"""
    # 检查是否有 bodyWithoutDocstring
    body = sample.get("bodyWithoutDocstring")
    if not body or not isinstance(body, str) or not body.strip():
        return None

    # 提取签名
    signature = _extract_signature(sample, code_field)
    if not signature:
        return None

    function_name = sample.get("functionName", "")

    return {
        "pairType": "signature_to_body",
        "instruction": INSTRUCTION_TEMPLATES["signature_to_body"],
        "input": signature,
        "output": body.strip(),
        "sourceFunctionName": function_name,
    }


def _build_code_to_docstring_pair(sample: dict, code_field: str, doc_field: str) -> Optional[dict]:
    """构造 code -> docstring pair"""
    # 检查是否有 docstring
    docstring = sample.get(doc_field) or sample.get("docstringInCode")
    if not docstring or not isinstance(docstring, str) or not docstring.strip():
        return None

    # 检查是否有 code
    code = sample.get(code_field, "")
    if not code or not isinstance(code, str):
        return None

    function_name = sample.get("functionName", "")

    return {
        "pairType": "code_to_docstring",
        "instruction": INSTRUCTION_TEMPLATES["code_to_docstring"],
        "input": code,
        "output": docstring.strip(),
        "sourceFunctionName": function_name,
    }


def _save_instruction_pairs(task_id: int, pairs: list[dict]) -> str:
    """保存 instruction pairs 到文件"""
    output_dir = Path(f"data/outputs/{task_id}").resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / "instruction_pairs.jsonl"

    with open(output_path, "w", encoding="utf-8") as f:
        for pair in pairs:
            f.write(json.dumps(pair, ensure_ascii=False) + "\n")

    return str(output_path)


@register("build_instruction_pairs")
def build_instruction_pairs(context: dict) -> dict:
    """构造 instruction pairs。真实实现。"""
    samples: list[dict] = context.get("samples", [])
    schema: dict = context.get("schema", {})
    options: dict = context.get("options", {})
    task_id: int = context.get("taskId", 0)

    code_field = schema.get("codeField", "")
    doc_field = schema.get("docstringField")

    enable_instruction_pairs = options.get("enableInstructionPairs", False)

    if not enable_instruction_pairs:
        n = len(samples)
        return {
            "samples": samples,
            "inputCount": n,
            "outputCount": n,
            "removedCount": 0,
            "instructionPairCount": 0,
            "docstringToCodeCount": 0,
            "signatureToBodyCount": 0,
            "codeToDocstringCount": 0,
            "skippedInstructionPairCount": 0,
            "status": "success",
            "message": "Instruction pairs 构造已禁用",
        }

    if not samples or not code_field:
        n = len(samples)
        return {
            "samples": samples,
            "inputCount": n,
            "outputCount": n,
            "removedCount": 0,
            "instructionPairCount": 0,
            "docstringToCodeCount": 0,
            "signatureToBodyCount": 0,
            "codeToDocstringCount": 0,
            "skippedInstructionPairCount": 0,
            "status": "success",
            "message": "无需构造（字段未配置）",
        }

    input_count = len(samples)
    all_pairs = []
    docstring_to_code_count = 0
    signature_to_body_count = 0
    code_to_docstring_count = 0
    skipped_count = 0

    for sample in samples:
        # 只处理解析成功的函数级样本
        if sample.get("parseOk") is not True:
            skipped_count += 1
            continue

        if not sample.get("functionName"):
            skipped_count += 1
            continue

        sample_has_pair = False

        # 1. 尝试构造 docstring_to_code
        if doc_field:
            pair = _build_docstring_to_code_pair(sample, code_field, doc_field)
            if pair:
                all_pairs.append(pair)
                docstring_to_code_count += 1
                sample_has_pair = True

        # 2. 尝试构造 signature_to_body
        pair = _build_signature_to_body_pair(sample, code_field)
        if pair:
            all_pairs.append(pair)
            signature_to_body_count += 1
            sample_has_pair = True

        # 3. 尝试构造 code_to_docstring
        if doc_field:
            pair = _build_code_to_docstring_pair(sample, code_field, doc_field)
            if pair:
                all_pairs.append(pair)
                code_to_docstring_count += 1
                sample_has_pair = True

        if not sample_has_pair:
            skipped_count += 1

    total_pair_count = len(all_pairs)

    # 保存 instruction pairs 到文件
    output_path = ""
    if all_pairs:
        output_path = _save_instruction_pairs(task_id, all_pairs)

    # 调试输出
    print(f"\n[DEBUG] build_instruction_pairs:")
    print(f"  输入样本: {input_count}")
    print(f"  总 pair 数: {total_pair_count}")
    print(f"    docstring_to_code: {docstring_to_code_count}")
    print(f"    signature_to_body: {signature_to_body_count}")
    print(f"    code_to_docstring: {code_to_docstring_count}")
    print(f"  跳过样本: {skipped_count}")
    if output_path:
        print(f"  输出文件: {output_path}")
    print()

    return {
        "samples": samples,  # 保持原样本不变
        "inputCount": input_count,
        "outputCount": input_count,
        "removedCount": 0,
        "instructionPairCount": total_pair_count,
        "docstringToCodeCount": docstring_to_code_count,
        "signatureToBodyCount": signature_to_body_count,
        "codeToDocstringCount": code_to_docstring_count,
        "skippedInstructionPairCount": skipped_count,
        "instructionPairsFile": output_path,
        "status": "success",
        "message": f"Instruction pairs 构造完成，共 {total_pair_count} 条（docstring->code: {docstring_to_code_count}, signature->body: {signature_to_body_count}, code->docstring: {code_to_docstring_count}）",
    }
