from skills.registry import registry

# Import all skill modules to trigger @register decorators
from skills import (
    detect_dataset_schema,
    load_dataset,
    normalize_code_text,
    extract_function_structure,
    filter_invalid_samples,
    filter_low_quality_docstring,
    deduplicate_samples,
    rename_variables_augmentation,
    build_instruction_pairs,
    compute_dataset_profile,
    evaluate_data_quality,
    generate_chart_specs,
)

__all__ = ["registry"]
