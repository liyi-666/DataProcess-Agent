from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from models import (
    PlanRequest, PlanResponse, DatasetSchema,
    ExecuteRequest, ExecuteResponse, Metrics, ChartSpec, ChartSeries, OutputFile, SkillExecutionLog,
    ChatRequest, ChatResponse,
    ParseIntentRequest, ParseIntentResponse,
)
from graph import agent_graph, execution_graph, hitl_graph, DEFAULT_EXECUTION_PLAN
from skills.registry import run_skill
from skills.llm_plan_advisor import llm_recommend_plan, rule_recommend_plan
from chat_handler import handle_chat
from skills.intent_parser import parse_user_intent

app = FastAPI(title="DataProcess PythonAgent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/agent/plan", response_model=PlanResponse)
def agent_plan(req: PlanRequest):
    thread_id = str(req.taskId)
    config = {"configurable": {"thread_id": thread_id}}

    plan = list(DEFAULT_EXECUTION_PLAN)
    if not req.options.enableAugmentation and "rename_variables_augmentation" in plan:
        plan.remove("rename_variables_augmentation")
    if not req.options.enableInstructionPairs and "build_instruction_pairs" in plan:
        plan.remove("build_instruction_pairs")

    initial_state = {
        "taskId": req.taskId,
        "filePath": req.filePath,
        "fileType": req.fileType,
        "schema": {},
        "options": req.options.model_dump(),
        "executionPlan": plan,
        "currentCount": 0,
        "rawSampleCount": 0,
        "samples": [],
        "metrics": {},
        "chartSpecs": [],
        "outputFiles": [],
        "executionLogs": [],
        "summary": "",
        "error": "",
        "reflectionSummary": "",
        "qualityWarnings": [],
        "nextStepSuggestions": [],
        "confirmPayload": {},
        "needUserConfirm": False,
        "datasetObservations": {},
    }

    # 启动 hitl_graph，运行到 waiting_confirm 节点的 interrupt 处暂停
    hitl_graph.invoke(initial_state, config)

    # 从 checkpoint 读取 interrupt 值和当前 state
    snap = hitl_graph.get_state(config)
    interrupt_value = snap.tasks[0].interrupts[0].value if snap.tasks else {}
    current_state = snap.values

    schema_data = current_state.get("schema", {})
    need_confirm = interrupt_value.get("needUserConfirm", False)
    task_status = "WAITING_CONFIRM" if need_confirm else "SCHEMA_DETECTING"

    # 推荐方案
    options_dict = req.options.model_dump()
    dataset_observations = current_state.get("datasetObservations", {})
    recommendation = llm_recommend_plan(
        task_description=req.taskDescription or "",
        detected_schema=schema_data,
        file_type=req.fileType,
        source_granularity=req.options.sourceGranularity,
        dataset_observations=dataset_observations,
    ) or rule_recommend_plan(
        task_description=req.taskDescription or "",
        detected_schema=schema_data,
        options_from_request=options_dict,
        dataset_observations=dataset_observations,
    )

    detected_schema = DatasetSchema(**schema_data) if schema_data.get("codeField") else DatasetSchema(
        codeField="",
        candidateCodeFields=schema_data.get("candidateCodeFields", []),
        candidateDocstringFields=schema_data.get("candidateDocstringFields", []),
        candidateLanguageFields=schema_data.get("candidateLanguageFields", []),
    )

    # 从实际样本分析构建 observedDatasetTraits
    observed_traits = []
    sample_count = dataset_observations.get("sampleCount", 0)
    if sample_count:
        observed_traits.append(f"已采样 {sample_count} 条样本进行分析")

    if schema_data.get("codeField"):
        observed_traits.append(f"检测到代码字段：{schema_data['codeField']}")
    if schema_data.get("docstringField"):
        observed_traits.append(f"检测到文档字段：{schema_data['docstringField']}")
    if schema_data.get("languageField"):
        observed_traits.append(f"检测到语言字段：{schema_data['languageField']}")

    if dataset_observations.get("codeFieldLooksLikeFunctions"):
        observed_traits.append("代码样本包含函数定义（检测到 def / class 关键字）")
    elif sample_count:
        observed_traits.append("代码样本未检测到函数定义，可能为代码片段或非 Python 代码")

    doc_coverage = dataset_observations.get("docstringCoverageEstimate")
    if doc_coverage is not None:
        observed_traits.append(f"docstring 覆盖率估计：{int(doc_coverage * 100)}%")

    avg_code_len = dataset_observations.get("avgCodeLength", 0)
    if avg_code_len:
        observed_traits.append(f"代码字段平均长度：{avg_code_len} 字符")

    detected_langs = dataset_observations.get("detectedLanguages", [])
    if detected_langs:
        observed_traits.append(f"检测到编程语言：{', '.join(detected_langs)}")

    if dataset_observations.get("nonStandardFields"):
        observed_traits.append("代码字段名称非标准，可能需要手动确认字段映射")

    candidate_code = schema_data.get("candidateCodeFields", [])
    if len(candidate_code) > 1:
        observed_traits.append(f"存在 {len(candidate_code)} 个候选代码字段，字段映射存在歧义")
    if not schema_data.get("docstringField"):
        observed_traits.append("未检测到 docstring 字段，instruction pairs 构造效果可能受限")
    if req.fileType == "parquet":
        observed_traits.append("输入为 Parquet 格式，读取效率较高")

    # 推荐模式（枚举值）
    rec_opts = recommendation.get("recommendedOptions", {})
    if rec_opts.get("enableAugmentation") and rec_opts.get("enableInstructionPairs"):
        recommended_mode = "enhanced_construction"
    elif rec_opts.get("enableInstructionPairs"):
        recommended_mode = "training_data_construction"
    else:
        recommended_mode = "cleaning_analysis"

    # 风险提示（结合样本分析）
    risk_warnings = []
    if not schema_data.get("docstringField"):
        risk_warnings.append("缺少 docstring 字段：过滤低质量文档和构造指令对的效果将受限")
    if len(candidate_code) > 1:
        risk_warnings.append("代码字段存在歧义：若字段选择错误，后续 AST 解析将大量失败")
    if req.options.enableAugmentation:
        risk_warnings.append("变量重命名增强依赖 AST 解析成功率，若语法通过率低则增强效果有限")
    if doc_coverage is not None and doc_coverage < 0.3:
        risk_warnings.append(f"docstring 覆盖率仅 {int(doc_coverage * 100)}%，低质量文档过滤后样本量可能大幅减少")
    if avg_code_len and avg_code_len < 50:
        risk_warnings.append(f"代码字段平均长度仅 {avg_code_len} 字符，样本可能为代码片段而非完整函数")
    if detected_langs and not any(l in ("python", "py") for l in detected_langs):
        risk_warnings.append(f"检测到非 Python 语言（{', '.join(detected_langs)}），AST 解析将失败，建议禁用 AST 相关步骤")
    if sample_count and not dataset_observations.get("codeFieldLooksLikeFunctions", True):
        risk_warnings.append("代码样本未检测到函数定义，extract_function_structure 步骤可能无法提取有效结构")

    return PlanResponse(
        taskId=req.taskId,
        taskStatus=task_status,
        needUserConfirm=need_confirm,
        confirmPayload=interrupt_value.get("confirmPayload"),
        detectedSchema=detected_schema,
        executionPlan=plan,
        recommendedOptions=recommendation["recommendedOptions"],
        recommendedExecutionPlan=recommendation["recommendedExecutionPlan"],
        recommendationReason=recommendation["recommendationReason"],
        observedDatasetTraits=observed_traits,
        recommendedMode=recommended_mode,
        riskWarnings=risk_warnings if risk_warnings else None,
    )


@app.post("/agent/execute", response_model=ExecuteResponse)
def agent_execute(req: ExecuteRequest):
    """
    执行预处理流程。
    若 hitl_graph 中存在该 taskId 的 checkpoint（即 /agent/plan 已启动过），
    则从 checkpoint 提取已保存的 state，合并用户确认的 schema/options/plan，
    直接走 execution_graph（绕开 interrupt/resume，避免 MemorySaver 在 anyio 线程池中死锁）。
    否则 fallback 到 execution_graph（向后兼容）。
    """
    thread_id = str(req.taskId)
    config = {"configurable": {"thread_id": thread_id}}

    snap = hitl_graph.get_state(config)
    has_checkpoint = bool(snap.values)

    print(f"[execute] taskId={req.taskId} has_checkpoint={has_checkpoint}", flush=True)
    print(f"[execute] req.options={req.options.model_dump()}", flush=True)
    print(f"[execute] req.executionPlan={req.executionPlan}", flush=True)

    if has_checkpoint:
        saved = snap.values
        print(f"[execute] using checkpoint state: filePath={saved.get('filePath')} fileType={saved.get('fileType')}", flush=True)
        initial_state = {
            "taskId": req.taskId,
            "filePath": saved.get("filePath", req.filePath),
            "fileType": saved.get("fileType", req.fileType),
            "schema": req.datasetSchema.model_dump(),
            "options": req.options.model_dump(),
            "executionPlan": req.executionPlan or DEFAULT_EXECUTION_PLAN,
            "currentCount": 0,
            "rawSampleCount": 0,
            "samples": [],
            "metrics": {},
            "chartSpecs": [],
            "outputFiles": [],
            "executionLogs": [],
            "summary": "",
            "error": "",
            "reflectionSummary": "",
            "qualityWarnings": [],
            "nextStepSuggestions": [],
            "confirmPayload": {},
            "needUserConfirm": False,
            "datasetObservations": saved.get("datasetObservations", {}),
            "_callbackUrl": req.callbackUrl or "",
        }
    else:
        initial_state = {
            "taskId": req.taskId,
            "filePath": req.filePath,
            "fileType": req.fileType,
            "schema": req.datasetSchema.model_dump(),
            "options": req.options.model_dump(),
            "executionPlan": req.executionPlan or DEFAULT_EXECUTION_PLAN,
            "currentCount": 0,
            "rawSampleCount": 0,
            "samples": [],
            "metrics": {},
            "chartSpecs": [],
            "outputFiles": [],
            "executionLogs": [],
            "summary": "",
            "error": "",
            "reflectionSummary": "",
            "qualityWarnings": [],
            "nextStepSuggestions": [],
            "confirmPayload": {},
            "needUserConfirm": False,
            "datasetObservations": {},
            "_callbackUrl": req.callbackUrl or "",
        }

    final_state = execution_graph.invoke(initial_state)

    raw = final_state.get("rawSampleCount", 0)
    final_count = final_state.get("currentCount", 0)
    m = final_state.get("metrics", {})

    metrics = Metrics(
        rawSampleCount=raw,
        finalSampleCount=final_count,
        retainRate=round(final_count / raw, 4) if raw else 0,
        astParseSuccessCount=m.get("astParseSuccessCount", 0),
        astParseFailedCount=m.get("astParseFailedCount", 0),
        emptyCodeCount=m.get("emptyCodeCount", 0),
        lowQualityDocstringCount=m.get("lowQualityDocstringCount", 0),
        dedupRemovedCount=m.get("dedupRemovedCount", 0),
        exactDedupRemovedCount=m.get("exactDedupRemovedCount", 0),
        astDedupRemovedCount=m.get("astDedupRemovedCount", 0),
        augmentationSuccessCount=m.get("augmentationSuccessCount", 0),
        augmentationFailedCount=m.get("augmentationFailedCount", 0),
        syntaxPassRate=m.get("syntaxPassRate", 0.0),
        docstringCoverage=m.get("docstringCoverage", 0.0),
        functionNameMatchRate=m.get("functionNameMatchRate", 0.0),
        returnAnnotationRate=m.get("returnAnnotationRate", 0.0),
        instructionPairCount=m.get("instructionPairCount", 0),
    )

    chart_specs = [ChartSpec(
        chartId=c["chartId"],
        chartType=c["chartType"],
        title=c["title"],
        xAxis=c["xAxis"],
        series=[ChartSeries(**s) for s in c["series"]],
    ) for c in final_state.get("chartSpecs", [])]

    output_files = [OutputFile(**f) for f in final_state.get("outputFiles", [])]
    logs = [SkillExecutionLog(**log) for log in final_state.get("executionLogs", [])]

    return ExecuteResponse(
        taskId=req.taskId,
        taskStatus="FINISHED",
        metrics=metrics,
        chartSpecs=chart_specs,
        outputFiles=output_files,
        executionLogs=logs,
        summary=final_state.get("summary", ""),
        reflectionSummary=final_state.get("reflectionSummary", ""),
        qualityWarnings=final_state.get("qualityWarnings", []),
        nextStepSuggestions=final_state.get("nextStepSuggestions", []),
    )


@app.post("/agent/chat", response_model=ChatResponse)
def agent_chat(req: ChatRequest):
    """基于真实 metrics 和 executionLogs 的规则化解释"""
    metrics = req.metrics or {}
    execution_logs = req.executionLogs or []
    summary = req.summary or ""

    reply, refer_metrics = handle_chat(
        task_id=req.taskId,
        message=req.message,
        metrics=metrics,
        execution_logs=execution_logs,
        summary=summary,
    )

    return ChatResponse(
        taskId=req.taskId,
        reply=reply,
        referMetrics=refer_metrics,
    )


@app.post("/agent/parse-intent", response_model=ParseIntentResponse)
def agent_parse_intent(req: ParseIntentRequest):
    action = parse_user_intent(
        message=req.userMessage,
        current_metrics=req.currentMetrics,
        current_options=req.currentOptions,
        summary=req.summary or "",
        reflection_summary=req.reflectionSummary or "",
        previous_refinement_action=req.previousRefinementAction,
    )
    return ParseIntentResponse(taskId=req.taskId, refinementAction=action)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
