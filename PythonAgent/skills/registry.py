from typing import Callable

_registry: dict[str, Callable] = {}


def register(name: str):
    def decorator(fn: Callable):
        _registry[name] = fn
        return fn
    return decorator


def run_skill(name: str, context: dict) -> dict:
    if name not in _registry:
        raise ValueError(f"Skill '{name}' not found in registry")
    return _registry[name](context)


def get_all_skill_names() -> list[str]:
    return list(_registry.keys())


# Import all skills to trigger registration
import skills.detect_dataset_schema  # noqa: E402, F401
import skills.load_dataset  # noqa: E402, F401
import skills.normalize_code_text  # noqa: E402, F401
import skills.extract_function_structure  # noqa: E402, F401
import skills.filter_invalid_samples  # noqa: E402, F401
import skills.filter_low_quality_docstring  # noqa: E402, F401
import skills.deduplicate_samples  # noqa: E402, F401
import skills.rename_variables_augmentation  # noqa: E402, F401
import skills.build_instruction_pairs  # noqa: E402, F401
import skills.compute_dataset_profile  # noqa: E402, F401
import skills.evaluate_data_quality  # noqa: E402, F401
import skills.generate_chart_specs  # noqa: E402, F401

registry = {
    "run": run_skill,
    "all_names": get_all_skill_names,
}
