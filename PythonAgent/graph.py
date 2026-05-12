import time
import json
import threading
import urllib.request
from pathlib import Path
from typing import Any, TypedDict
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt
from skills.registry import run_skill
from skills.reflection import run_reflection


DEFAULT_EXECUTION_PLAN = [
    "load_dataset",
    "normalize_code_text",
    "extract_function_structure",
    "filter_invalid_samples",
    "filter_low_quality_docstring",
    "deduplicate_samples",
    "rename_variables_augmentation",
    "build_instruction_pairs",
    "compute_dataset_profile",
    "evaluate_data_quality",
    "generate_chart_specs",
]


def _fire_callback(url: str, payload: dict) -> None:
    """非阻塞发送进度回调，失败静默忽略。"""
    if not url:
        return

    def _send():
        try:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json; charset=UTF-8"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=3)
        except Exception as e:
            print(f"[callback] warn: {e}", flush=True)

    threading.Thread(target=_send, daemon=True).start()


class AgentState(TypedDict):
    taskId: int
    filePath: str
    fileType: str
    schema: dict
    options: dict
    executionPlan: list[str]
    currentCount: int
    rawSampleCount: int
    samples: list
    metrics: dict
    chartSpecs: list
    outputFiles: list
    executionLogs: list
    summary: str
    error: str
    reflectionSummary: str
    qualityWarnings: list
    nextStepSuggestions: list
    confirmPayload: dict
    needUserConfirm: bool
    datasetObservations: dict
    _callbackUrl: str


def node_schema_detect(state: AgentState) -> AgentState:
    result = run_skill("detect_dataset_schema", state)
    schema_data = result.get("detectedSchema", state["schema"])
    need_confirm = result.get("needUserConfirm", False)
    confirm_payload = result.get("confirmPayload", {}) or {}
    dataset_observations = result.get("datasetObservations", {})
    return {
        **state,
        "schema": schema_data,
        "needUserConfirm": need_confirm,
        "confirmPayload": confirm_payload,
        "datasetObservations": dataset_observations,
    }


def node_waiting_confirm(state: AgentState) -> AgentState:
    """
    HITL 节点：schema 不明确时 interrupt 等待用户确认；
    schema 明确时也 interrupt，作为 plan/execute 的分界点。
    resume 值为用户确认的 schema 字段 dict（或空 dict 表示无修改）。
    """
    schema = state.get("schema", {})
    need_confirm = state.get("needUserConfirm", False)

    confirmed = interrupt({
        "needUserConfirm": need_confirm,
        "confirmPayload": state.get("confirmPayload") if need_confirm else None,
    })

    # resume 后 state 已包含 update_state 写入的最新 options/executionPlan，直接用 state
    if confirmed and isinstance(confirmed, dict):
        return {**state, "schema": {**schema, **confirmed}}
    return state


def node_preprocess(state: AgentState) -> AgentState:
    preprocess_skills = [
        "load_dataset",
        "normalize_code_text",
        "extract_function_structure",
        "filter_invalid_samples",
        "filter_low_quality_docstring",
        "deduplicate_samples",
        "rename_variables_augmentation",
        "build_instruction_pairs",
    ]
    plan = state.get("executionPlan", DEFAULT_EXECUTION_PLAN)
    callback_url = state.get("_callbackUrl", "")
    task_id = state.get("taskId")
    print(f"[node_preprocess] executionPlan={plan}", flush=True)
    print(f"[node_preprocess] options={state.get('options', {})}", flush=True)
    logs = list(state.get("executionLogs", []))
    current_count = state.get("currentCount", 0)
    raw_count = 0
    accumulated_metrics: dict[str, Any] = {}
    samples: list = list(state.get("samples", []))

    active_skills = [s for s in plan if s in preprocess_skills]
    total_skills = len([s for s in plan if s in preprocess_skills + [
        "compute_dataset_profile", "evaluate_data_quality", "generate_chart_specs"
    ]])
    skill_index = 0

    for skill_name in plan:
        if skill_name not in preprocess_skills:
            continue
        progress = 10 + int(skill_index / max(total_skills, 1) * 85)
        _fire_callback(callback_url, {
            "taskId": task_id,
            "event": "skill_start",
            "skillName": skill_name,
            "progress": progress,
            "inputCount": current_count,
            "outputCount": 0,
            "durationMs": 0,
            "message": "",
        })
        start = time.time()
        print(f"[TIMING] >>> {skill_name} start | samples={len(samples)} | schema.codeField={state.get('schema', {}).get('codeField', '(empty)')!r}", flush=True)
        if skill_name == "extract_function_structure" and samples:
            _s0 = samples[0]
            print(f"[TIMING]     sample[0] keys={list(_s0.keys())}", flush=True)
            print(f"[TIMING]     has 'code'={('code' in _s0)} has 'original_string'={('original_string' in _s0)}", flush=True)
            print(f"[TIMING]     loky threshold check: len(samples)={len(samples)} >= {2000}? {len(samples) >= 2000}", flush=True)
        ctx = {**state, "currentCount": current_count, "samples": samples}
        result = run_skill(skill_name, ctx)
        elapsed = int((time.time() - start) * 1000)
        print(f"[TIMING] <<< {skill_name} done in {elapsed / 1000:.1f}s | out={result.get('outputCount', len(result.get('samples', samples)))}", flush=True)

        # update samples if skill returned new data
        if "samples" in result:
            samples = result["samples"]

        if skill_name == "load_dataset":
            raw_count = result.get("rawSampleCount", len(samples))
            current_count = raw_count
        else:
            current_count = result.get("outputCount", len(samples))

        accumulated_metrics.update({k: v for k, v in result.items()
                                     if k not in ("inputCount", "outputCount", "removedCount",
                                                  "status", "message", "samples", "rawSampleCount")})
        log_entry = {
            "skillName": skill_name,
            "status": result.get("status", "success"),
            "inputCount": result.get("inputCount", 0),
            "outputCount": result.get("outputCount", 0),
            "removedCount": result.get("removedCount", 0),
            "durationMs": elapsed,
            "message": result.get("message", ""),
        }
        logs.append(log_entry)

        skill_index += 1
        progress_done = 10 + int(skill_index / max(total_skills, 1) * 85)
        _fire_callback(callback_url, {
            "taskId": task_id,
            "event": "skill_done",
            "skillName": skill_name,
            "progress": progress_done,
            "inputCount": log_entry["inputCount"],
            "outputCount": log_entry["outputCount"],
            "durationMs": elapsed,
            "message": log_entry["message"],
        })

    return {
        **state,
        "samples": samples,
        "currentCount": current_count,
        "rawSampleCount": raw_count,
        "executionLogs": logs,
        "metrics": {**state.get("metrics", {}), **accumulated_metrics},
    }


def node_analyze(state: AgentState) -> AgentState:
    plan = state.get("executionPlan", DEFAULT_EXECUTION_PLAN)
    callback_url = state.get("_callbackUrl", "")
    task_id = state.get("taskId")
    logs = list(state.get("executionLogs", []))
    metrics = dict(state.get("metrics", {}))

    total_skills = len([s for s in plan if s in [
        "load_dataset", "normalize_code_text", "extract_function_structure",
        "filter_invalid_samples", "filter_low_quality_docstring", "deduplicate_samples",
        "rename_variables_augmentation", "build_instruction_pairs",
        "compute_dataset_profile", "evaluate_data_quality", "generate_chart_specs",
    ]])
    preprocess_done = len([s for s in plan if s in [
        "load_dataset", "normalize_code_text", "extract_function_structure",
        "filter_invalid_samples", "filter_low_quality_docstring", "deduplicate_samples",
        "rename_variables_augmentation", "build_instruction_pairs",
    ]])

    for i, skill_name in enumerate(["compute_dataset_profile", "evaluate_data_quality"]):
        if skill_name not in plan:
            continue
        skill_index = preprocess_done + i
        progress = 10 + int(skill_index / max(total_skills, 1) * 85)
        _fire_callback(callback_url, {
            "taskId": task_id,
            "event": "skill_start",
            "skillName": skill_name,
            "progress": progress,
            "inputCount": state.get("currentCount", 0),
            "outputCount": 0,
            "durationMs": 0,
            "message": "",
        })
        start = time.time()
        ctx = {**state, "currentCount": state.get("currentCount", 0),
               "rawSampleCount": state.get("rawSampleCount", 0),
               "metrics": metrics}
        result = run_skill(skill_name, ctx)
        elapsed = int((time.time() - start) * 1000)

        if "profile" in result:
            metrics.update(result["profile"])
        if "qualityMetrics" in result:
            metrics.update(result["qualityMetrics"])

        log_entry = {
            "skillName": skill_name,
            "status": result.get("status", "success"),
            "inputCount": result.get("inputCount", 0),
            "outputCount": result.get("outputCount", 0),
            "removedCount": 0,
            "durationMs": elapsed,
            "message": result.get("message", ""),
        }
        logs.append(log_entry)

        progress_done = 10 + int((skill_index + 1) / max(total_skills, 1) * 85)
        _fire_callback(callback_url, {
            "taskId": task_id,
            "event": "skill_done",
            "skillName": skill_name,
            "progress": progress_done,
            "inputCount": log_entry["inputCount"],
            "outputCount": log_entry["outputCount"],
            "durationMs": elapsed,
            "message": log_entry["message"],
        })

    return {**state, "metrics": metrics, "executionLogs": logs}


def node_visualize(state: AgentState) -> AgentState:
    plan = state.get("executionPlan", DEFAULT_EXECUTION_PLAN)
    if "generate_chart_specs" not in plan:
        return state

    callback_url = state.get("_callbackUrl", "")
    task_id = state.get("taskId")
    _fire_callback(callback_url, {
        "taskId": task_id,
        "event": "skill_start",
        "skillName": "generate_chart_specs",
        "progress": 95,
        "inputCount": 0,
        "outputCount": 0,
        "durationMs": 0,
        "message": "",
    })

    ctx = {**state, "currentCount": state.get("currentCount", 0),
           "rawSampleCount": state.get("rawSampleCount", 0)}
    start = time.time()
    result = run_skill("generate_chart_specs", ctx)
    elapsed = int((time.time() - start) * 1000)

    logs = list(state.get("executionLogs", []))
    log_entry = {
        "skillName": "generate_chart_specs",
        "status": result.get("status", "success"),
        "inputCount": 0,
        "outputCount": 0,
        "removedCount": 0,
        "durationMs": elapsed,
        "message": result.get("message", ""),
    }
    logs.append(log_entry)

    _fire_callback(callback_url, {
        "taskId": task_id,
        "event": "skill_done",
        "skillName": "generate_chart_specs",
        "progress": 97,
        "inputCount": 0,
        "outputCount": 0,
        "durationMs": elapsed,
        "message": log_entry["message"],
    })

    return {**state, "chartSpecs": result.get("chartSpecs", []), "executionLogs": logs}


def node_summary(state: AgentState) -> AgentState:
    raw = state.get("rawSampleCount", 0)
    final = state.get("currentCount", 0)
    task_id = state.get("taskId")
    samples = state.get("samples", [])
    callback_url = state.get("_callbackUrl", "")

    # 构建输出路径
    output_dir = Path(f"data/outputs/{task_id}").resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / "processed_dataset.jsonl"

    # 写入 JSONL 文件
    with open(output_file, "w", encoding="utf-8", errors="replace") as f:
        for sample in samples:
            f.write(json.dumps(sample, ensure_ascii=False) + "\n")

    output_path = str(output_file)
    output_files = [{
        "fileRole": "cleaned",
        "fileName": "processed_dataset.jsonl",
        "filePath": output_path,
        "fileUrl": None,
    }]

    options = state.get("options", {})
    plan = state.get("executionPlan", [])
    if options.get("enableInstructionPairs") and "build_instruction_pairs" in plan:
        pairs_file = output_dir / "instruction_pairs.jsonl"
        if pairs_file.exists():
            output_files.append({
                "fileRole": "instruction_pairs",
                "fileName": "instruction_pairs.jsonl",
                "filePath": str(pairs_file),
                "fileUrl": None,
            })
    summary = f"任务执行完成，原始样本 {raw} 条，共保留 {final} 条有效样本。"

    reflection = run_reflection(
        metrics=state.get("metrics", {}),
        execution_logs=state.get("executionLogs", []),
        summary=summary,
        options=state.get("options", {}),
    )

    _fire_callback(callback_url, {
        "taskId": task_id,
        "event": "task_done",
        "skillName": "summarize",
        "progress": 100,
        "inputCount": raw,
        "outputCount": final,
        "durationMs": 0,
        "message": summary,
    })

    return {
        **state,
        "outputFiles": output_files,
        "summary": summary,
        "reflectionSummary": reflection.get("reflectionSummary", ""),
        "qualityWarnings": reflection.get("qualityWarnings", []),
        "nextStepSuggestions": reflection.get("nextStepSuggestions", []),
    }


def build_graph() -> StateGraph:
    """构建完整 graph，从 schema_detect 开始（无 checkpointer，旧版兼容）"""
    graph = StateGraph(AgentState)
    graph.add_node("schema_detect", node_schema_detect)
    graph.add_node("preprocess", node_preprocess)
    graph.add_node("analyze", node_analyze)
    graph.add_node("visualize", node_visualize)
    graph.add_node("summarize", node_summary)

    graph.set_entry_point("schema_detect")
    graph.add_edge("schema_detect", "preprocess")
    graph.add_edge("preprocess", "analyze")
    graph.add_edge("analyze", "visualize")
    graph.add_edge("visualize", "summarize")
    graph.add_edge("summarize", END)

    return graph.compile()


def build_execution_graph() -> StateGraph:
    """构建执行 graph，从 preprocess 开始（用于 schema 已确认的场景）"""
    graph = StateGraph(AgentState)
    graph.add_node("preprocess", node_preprocess)
    graph.add_node("analyze", node_analyze)
    graph.add_node("visualize", node_visualize)
    graph.add_node("summarize", node_summary)

    graph.set_entry_point("preprocess")
    graph.add_edge("preprocess", "analyze")
    graph.add_edge("analyze", "visualize")
    graph.add_edge("visualize", "summarize")
    graph.add_edge("summarize", END)

    return graph.compile()


_checkpointer = MemorySaver()


def build_hitl_graph():
    """
    带 HITL 的完整 graph：
    schema_detect -> waiting_confirm (interrupt) -> preprocess -> analyze -> visualize -> summarize
    使用 MemorySaver checkpointer 持久化 state，支持 interrupt/resume。
    """
    graph = StateGraph(AgentState)
    graph.add_node("schema_detect", node_schema_detect)
    graph.add_node("waiting_confirm", node_waiting_confirm)
    graph.add_node("preprocess", node_preprocess)
    graph.add_node("analyze", node_analyze)
    graph.add_node("visualize", node_visualize)
    graph.add_node("summarize", node_summary)

    graph.set_entry_point("schema_detect")
    graph.add_edge("schema_detect", "waiting_confirm")
    graph.add_edge("waiting_confirm", "preprocess")
    graph.add_edge("preprocess", "analyze")
    graph.add_edge("analyze", "visualize")
    graph.add_edge("visualize", "summarize")
    graph.add_edge("summarize", END)

    return graph.compile(checkpointer=_checkpointer)


agent_graph = build_graph()
execution_graph = build_execution_graph()
hitl_graph = build_hitl_graph()
