import ast
import os
from typing import Optional

from joblib import Parallel, delayed
from skills.registry import register

_N_JOBS = min(os.cpu_count() or 4, 8)
_PARALLEL_THRESHOLD = 2000


def _extract_docstring(node: ast.FunctionDef | ast.AsyncFunctionDef) -> Optional[str]:
    return ast.get_docstring(node)


def _get_body_without_docstring(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    body = node.body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        if isinstance(body[0].value.value, str):
            body = body[1:]
    if not body:
        return "pass"
    try:
        return "\n".join(ast.unparse(stmt) for stmt in body)
    except Exception:
        return "# unparse failed"


def _extract_function_info(node: ast.FunctionDef | ast.AsyncFunctionDef) -> dict:
    try:
        return {
            "functionName": node.name,
            "parameters": [arg.arg for arg in node.args.args],
            "returnAnnotation": ast.unparse(node.returns) if node.returns else None,
            "docstringInCode": _extract_docstring(node),
            "bodyWithoutDocstring": _get_body_without_docstring(node),
            "isAsync": isinstance(node, ast.AsyncFunctionDef),
            "parseOk": True,
            "errorMessage": None,
        }
    except Exception as e:
        return {
            "functionName": None, "parameters": [], "returnAnnotation": None,
            "docstringInCode": None, "bodyWithoutDocstring": None,
            "isAsync": False, "parseOk": False, "errorMessage": f"提取函数信息失败: {e}",
        }


def _process_single_sample(sample: dict, code_field: str) -> list[dict]:
    code = sample.get(code_field, "")
    _fail = lambda msg: [{
        **sample,
        "functionName": None, "parameters": [], "returnAnnotation": None,
        "docstringInCode": None, "bodyWithoutDocstring": None,
        "isAsync": False, "parseOk": False, "errorMessage": msg,
        "astDump": None,
    }]

    if not code or not isinstance(code, str):
        return _fail("代码字段为空或非字符串")

    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return _fail(f"语法错误: {e}")
    except Exception as e:
        return _fail(f"AST 解析失败: {e}")

    functions = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]

    if not functions:
        return _fail("未找到函数定义")

    if len(functions) == 1:
        func_info = _extract_function_info(functions[0])
        # 存储 ast.dump 供去重复用，避免二次解析
        try:
            func_info["astDump"] = ast.dump(functions[0], include_attributes=False)
        except Exception:
            func_info["astDump"] = None
        return [{**sample, **func_info}]

    result = []
    for func_node in functions:
        func_info = _extract_function_info(func_node)
        new_sample = {**sample}
        try:
            new_sample[code_field] = ast.unparse(func_node)
        except Exception:
            pass
        try:
            func_info["astDump"] = ast.dump(func_node, include_attributes=False)
        except Exception:
            func_info["astDump"] = None
        new_sample.update(func_info)
        result.append(new_sample)
    return result


def _process_chunk(args: tuple) -> list[dict]:
    chunk, code_field = args
    out = []
    for sample in chunk:
        out.extend(_process_single_sample(sample, code_field))
    return out


@register("extract_function_structure")
def extract_function_structure(context: dict) -> dict:
    samples: list[dict] = context.get("samples", [])
    schema: dict = context.get("schema", {})
    options: dict = context.get("options", {})
    code_field = schema.get("codeField", "")

    if not options.get("enableAstExtract", True):
        n = len(samples)
        return {
            "samples": samples, "inputCount": n, "outputCount": n, "removedCount": 0,
            "astParseSuccessCount": 0, "astParseFailedCount": 0,
            "status": "success", "message": "AST 提取已关闭（enableAstExtract=false）",
        }

    if not samples or not code_field:
        n = len(samples)
        return {
            "samples": samples, "inputCount": n, "outputCount": n, "removedCount": 0,
            "astParseSuccessCount": 0, "astParseFailedCount": 0,
            "status": "success", "message": "无需处理（字段未配置）",
        }

    input_count = len(samples)

    if input_count >= _PARALLEL_THRESHOLD:
        chunk_size = max(500, input_count // (_N_JOBS * 4))
        chunks = [samples[i:i + chunk_size] for i in range(0, input_count, chunk_size)]
        # loky 后端不依赖 __main__，在 uvicorn 进程内安全使用
        batch_results = Parallel(n_jobs=_N_JOBS, backend="loky")(
            delayed(_process_chunk)((chunk, code_field)) for chunk in chunks
        )
        processed = [s for batch in batch_results for s in batch]
        workers_used = _N_JOBS
    else:
        processed = []
        for sample in samples:
            processed.extend(_process_single_sample(sample, code_field))
        workers_used = 1

    success_count = sum(1 for s in processed if s.get("parseOk", False))
    failed_count = len(processed) - success_count
    output_count = len(processed)

    print(f"\n[DEBUG] extract_function_structure: 输入={input_count} 输出={output_count} "
          f"成功={success_count} 失败={failed_count} workers={workers_used}")

    return {
        "samples": processed,
        "inputCount": input_count,
        "outputCount": output_count,
        "removedCount": 0,
        "astParseSuccessCount": success_count,
        "astParseFailedCount": failed_count,
        "status": "success",
        "message": f"AST 解析完成，成功 {success_count} 条，失败 {failed_count} 条",
    }
