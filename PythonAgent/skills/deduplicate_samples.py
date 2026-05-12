import ast
import hashlib

from skills.registry import register


def _compute_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _exact_dedup(samples: list[dict], code_field: str) -> tuple[list[dict], int]:
    seen_hashes: set[str] = set()
    unique_samples = []
    removed_count = 0

    for sample in samples:
        code = sample.get(code_field, "")
        if not code or not isinstance(code, str):
            unique_samples.append(sample)
            continue
        code_hash = _compute_hash(code)
        if code_hash in seen_hashes:
            removed_count += 1
        else:
            seen_hashes.add(code_hash)
            unique_samples.append(sample)

    return unique_samples, removed_count


def _ast_dedup(samples: list[dict], code_field: str) -> tuple[list[dict], int]:
    """
    AST 去重：优先复用 extract_function_structure 写入的 astDump 字段，
    避免对 152k 行数据做第二次全量 ast.parse。
    """
    seen_ast_hashes: set[str] = set()
    unique_samples = []
    removed_count = 0

    for sample in samples:
        if sample.get("parseOk") is not True:
            unique_samples.append(sample)
            continue

        # 优先使用已缓存的 astDump
        ast_repr: str | None = sample.get("astDump")
        if ast_repr is None:
            code = sample.get(code_field, "")
            if not code or not isinstance(code, str):
                unique_samples.append(sample)
                continue
            try:
                tree = ast.parse(code)
                ast_repr = ast.dump(tree, include_attributes=False)
            except Exception:
                unique_samples.append(sample)
                continue

        ast_hash = _compute_hash(ast_repr)
        if ast_hash in seen_ast_hashes:
            removed_count += 1
        else:
            seen_ast_hashes.add(ast_hash)
            unique_samples.append(sample)

    return unique_samples, removed_count


@register("deduplicate_samples")
def deduplicate_samples(context: dict) -> dict:
    """精确去重和 AST 去重。真实实现。"""
    samples: list[dict] = context.get("samples", [])
    schema: dict = context.get("schema", {})
    options: dict = context.get("options", {})
    code_field = schema.get("codeField", "")

    enable_dedup = options.get("enableDedup", True)
    enable_ast_dedup = options.get("enableAstDedup", True)

    if not samples or not code_field:
        n = len(samples)
        return {
            "samples": samples,
            "inputCount": n,
            "outputCount": n,
            "removedCount": 0,
            "dedupRemovedCount": 0,
            "exactDedupRemovedCount": 0,
            "astDedupRemovedCount": 0,
            "status": "success",
            "message": "无需去重（字段未配置）",
        }

    if not enable_dedup:
        n = len(samples)
        return {
            "samples": samples,
            "inputCount": n,
            "outputCount": n,
            "removedCount": 0,
            "dedupRemovedCount": 0,
            "exactDedupRemovedCount": 0,
            "astDedupRemovedCount": 0,
            "status": "success",
            "message": "去重已禁用",
        }

    input_count = len(samples)
    exact_removed = 0
    ast_removed = 0

    # 1. 精确去重
    samples, exact_removed = _exact_dedup(samples, code_field)

    # 2. AST 去重（如果启用）
    if enable_ast_dedup:
        samples, ast_removed = _ast_dedup(samples, code_field)

    output_count = len(samples)
    total_removed = exact_removed + ast_removed

    # 调试输出
    print(f"\n[DEBUG] deduplicate_samples:")
    print(f"  输入样本: {input_count}")
    print(f"  输出样本: {output_count}")
    print(f"  总去重数: {total_removed}")
    print(f"    精确去重: {exact_removed}")
    print(f"    AST 去重: {ast_removed}")
    print()

    return {
        "samples": samples,
        "inputCount": input_count,
        "outputCount": output_count,
        "removedCount": total_removed,
        "dedupRemovedCount": total_removed,
        "exactDedupRemovedCount": exact_removed,
        "astDedupRemovedCount": ast_removed,
        "status": "success",
        "message": f"去重完成，保留 {output_count}/{input_count} 条（精确去重 {exact_removed}，AST 去重 {ast_removed}）",
    }
