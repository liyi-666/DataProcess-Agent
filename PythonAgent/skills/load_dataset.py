import csv
import json

from skills.registry import register


def _load(file_path: str, file_type: str) -> list[dict]:
    ft = file_type.lower()

    if ft == "jsonl":
        rows = []
        with open(file_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
        return rows

    if ft == "csv":
        with open(file_path, encoding="utf-8", newline="") as f:
            return [dict(row) for row in csv.DictReader(f)]

    if ft == "parquet":
        import pandas as pd
        df = pd.read_parquet(file_path)
        return json.loads(df.to_json(orient="records", force_ascii=False))

    raise ValueError(f"不支持的文件类型: {file_type}")


@register("load_dataset")
def load_dataset(context: dict) -> dict:
    file_path: str = context.get("filePath", "")
    file_type: str = context.get("fileType", "")

    try:
        samples = _load(file_path, file_type)
    except Exception as e:
        return {
            "rawSampleCount": 0,
            "samples": [],
            "inputCount": 0,
            "outputCount": 0,
            "removedCount": 0,
            "status": "error",
            "message": f"加载失败: {e}",
        }

    n = len(samples)
    return {
        "rawSampleCount": n,
        "samples": samples,
        "inputCount": 0,
        "outputCount": n,
        "removedCount": 0,
        "status": "success",
        "message": f"数据集加载完成，共 {n} 条样本",
    }
