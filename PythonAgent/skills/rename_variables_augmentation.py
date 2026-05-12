import ast
import hashlib
from typing import Optional

from skills.registry import register


class LocalVariableRenamer(ast.NodeTransformer):
    """局部变量重命名转换器"""

    def __init__(self, rename_map: dict[str, str]):
        self.rename_map = rename_map

    def visit_Name(self, node: ast.Name) -> ast.Name:
        """重命名变量引用"""
        if node.id in self.rename_map:
            node.id = self.rename_map[node.id]
        return node


def _find_local_variables(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    """
    找出函数体内的局部变量（不包括参数、函数名、全局变量等）

    当前版本只识别：
    - 赋值语句左侧的变量
    - for 循环变量
    - with as 变量
    """
    local_vars = set()

    # 获取参数名（不应被重命名）
    param_names = {arg.arg for arg in func_node.args.args}
    if func_node.args.vararg:
        param_names.add(func_node.args.vararg.arg)
    if func_node.args.kwarg:
        param_names.add(func_node.args.kwarg.arg)

    # 遍历函数体
    for node in ast.walk(func_node):
        # 赋值语句
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    if target.id not in param_names:
                        local_vars.add(target.id)

        # for 循环变量
        elif isinstance(node, ast.For):
            if isinstance(node.target, ast.Name):
                if node.target.id not in param_names:
                    local_vars.add(node.target.id)

        # with as 变量
        elif isinstance(node, ast.With):
            for item in node.items:
                if item.optional_vars and isinstance(item.optional_vars, ast.Name):
                    if item.optional_vars.id not in param_names:
                        local_vars.add(item.optional_vars.id)

        # AugAssign (+=, -=, etc.)
        elif isinstance(node, ast.AugAssign):
            if isinstance(node.target, ast.Name):
                if node.target.id not in param_names:
                    local_vars.add(node.target.id)

    return local_vars


def _generate_rename_map(local_vars: set[str]) -> dict[str, str]:
    """
    为局部变量生成重命名映射

    当前策略：var_1, var_2, var_3, ...
    """
    if not local_vars:
        return {}

    # 排序保证稳定性
    sorted_vars = sorted(local_vars)
    rename_map = {}

    for i, var_name in enumerate(sorted_vars, start=1):
        # 跳过已经是 var_N 格式的变量
        if var_name.startswith("var_") and var_name[4:].isdigit():
            continue
        rename_map[var_name] = f"var_{i}"

    return rename_map


def _augment_single_sample(sample: dict, code_field: str) -> Optional[dict]:
    """
    对单个样本进行变量重命名增强

    Returns:
        增强后的样本，如果增强失败则返回 None
    """
    # 只处理解析成功的函数级样本
    if sample.get("parseOk") is not True:
        return None

    if not sample.get("functionName"):
        return None

    code = sample.get(code_field, "")
    if not code or not isinstance(code, str):
        return None

    try:
        # 解析代码
        tree = ast.parse(code)

        # 找到函数定义
        func_nodes = [node for node in tree.body
                      if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]

        if not func_nodes:
            return None

        func_node = func_nodes[0]  # 取第一个函数

        # 找出局部变量
        local_vars = _find_local_variables(func_node)

        if not local_vars:
            # 没有局部变量，无需增强
            return None

        # 生成重命名映射
        rename_map = _generate_rename_map(local_vars)

        if not rename_map:
            # 没有需要重命名的变量
            return None

        # 应用重命名
        renamer = LocalVariableRenamer(rename_map)
        new_tree = renamer.visit(tree)

        # 生成新代码
        new_code = ast.unparse(new_tree)

        # 校验新代码
        ast.parse(new_code)

        # 创建增强样本
        augmented_sample = dict(sample)
        augmented_sample[code_field] = new_code

        return augmented_sample

    except Exception:
        # 增强失败，返回 None
        return None


def _compute_hash(text: str) -> str:
    """计算文本的 SHA256 哈希"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@register("rename_variables_augmentation")
def rename_variables_augmentation(context: dict) -> dict:
    """变量重命名增强。真实实现。"""
    samples: list[dict] = context.get("samples", [])
    schema: dict = context.get("schema", {})
    options: dict = context.get("options", {})
    code_field = schema.get("codeField", "")

    enable_augmentation = options.get("enableAugmentation", False)

    if not enable_augmentation:
        n = len(samples)
        return {
            "samples": samples,
            "inputCount": n,
            "outputCount": n,
            "removedCount": 0,
            "augmentationAttemptCount": 0,
            "augmentationSuccessCount": 0,
            "augmentationFailedCount": 0,
            "augmentationDuplicateDroppedCount": 0,
            "status": "success",
            "message": "变量重命名增强已禁用",
        }

    if not samples or not code_field:
        n = len(samples)
        return {
            "samples": samples,
            "inputCount": n,
            "outputCount": n,
            "removedCount": 0,
            "augmentationAttemptCount": 0,
            "augmentationSuccessCount": 0,
            "augmentationFailedCount": 0,
            "augmentationDuplicateDroppedCount": 0,
            "status": "success",
            "message": "无需增强（字段未配置）",
        }

    input_count = len(samples)
    attempt_count = 0
    success_count = 0
    failed_count = 0
    duplicate_dropped_count = 0

    # 收集原始样本的代码哈希（用于去重）
    existing_hashes = set()
    for sample in samples:
        code = sample.get(code_field, "")
        if code and isinstance(code, str):
            existing_hashes.add(_compute_hash(code))

    # 增强样本列表
    augmented_samples = []

    for sample in samples:
        # 尝试增强
        attempt_count += 1
        augmented = _augment_single_sample(sample, code_field)

        if augmented is None:
            # 增强失败
            failed_count += 1
            continue

        # 检查是否与已有样本重复
        new_code = augmented.get(code_field, "")
        new_hash = _compute_hash(new_code)

        if new_hash in existing_hashes:
            # 重复，丢弃
            duplicate_dropped_count += 1
            continue

        # 增强成功
        success_count += 1
        existing_hashes.add(new_hash)
        augmented_samples.append(augmented)

    # 合并原始样本和增强样本
    all_samples = samples + augmented_samples
    output_count = len(all_samples)

    # 调试输出
    print(f"\n[DEBUG] rename_variables_augmentation:")
    print(f"  输入样本: {input_count}")
    print(f"  尝试增强: {attempt_count}")
    print(f"  增强成功: {success_count}")
    print(f"  增强失败: {failed_count}")
    print(f"  重复丢弃: {duplicate_dropped_count}")
    print(f"  输出样本: {output_count}")
    print()

    return {
        "samples": all_samples,
        "inputCount": input_count,
        "outputCount": output_count,
        "removedCount": 0,
        "augmentationAttemptCount": attempt_count,
        "augmentationSuccessCount": success_count,
        "augmentationFailedCount": failed_count,
        "augmentationDuplicateDroppedCount": duplicate_dropped_count,
        "status": "success",
        "message": f"变量重命名增强完成，成功 {success_count} 条，失败 {failed_count} 条，重复丢弃 {duplicate_dropped_count} 条",
    }
