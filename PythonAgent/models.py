from typing import Any, Optional
from pydantic import BaseModel, Field


class ProcessingOptions(BaseModel):
    enableDedup: bool = True
    enableAstDedup: bool = True
    enableAstExtract: bool = True
    enableAugmentation: bool = False
    enableInstructionPairs: bool = True
    sampleUnitType: str = "function"
    sourceGranularity: str = "function"


class DatasetSchema(BaseModel):
    codeField: str
    docstringField: Optional[str] = None
    languageField: Optional[str] = None
    candidateCodeFields: list[str] = []
    candidateDocstringFields: list[str] = []
    candidateLanguageFields: list[str] = []


class PlanRequest(BaseModel):
    taskId: int
    filePath: str
    fileType: str
    taskDescription: Optional[str] = None
    options: ProcessingOptions = ProcessingOptions()


class PlanResponse(BaseModel):
    taskId: int
    taskStatus: str
    needUserConfirm: bool
    confirmPayload: Optional[dict] = None
    detectedSchema: DatasetSchema
    executionPlan: list[str]
    # 推荐方案
    recommendedOptions: Optional[dict] = None
    recommendedExecutionPlan: Optional[list[str]] = None
    recommendationReason: Optional[str] = None
    # 规划信息（Agent 行为感）
    observedDatasetTraits: Optional[list[str]] = None
    recommendedMode: Optional[str] = None
    riskWarnings: Optional[list[str]] = None


class ExecuteRequest(BaseModel):
    model_config = {"populate_by_name": True}

    taskId: int
    filePath: str
    fileType: str
    datasetSchema: DatasetSchema = Field(alias="schema")
    options: ProcessingOptions = ProcessingOptions()
    executionPlan: Optional[list[str]] = None
    callbackUrl: Optional[str] = None


class Metrics(BaseModel):
    rawSampleCount: int = 0
    finalSampleCount: int = 0
    retainRate: float = 0.0
    astParseSuccessCount: int = 0
    astParseFailedCount: int = 0
    emptyCodeCount: int = 0
    lowQualityDocstringCount: int = 0
    dedupRemovedCount: int = 0
    exactDedupRemovedCount: int = 0
    astDedupRemovedCount: int = 0
    augmentationSuccessCount: int = 0
    augmentationFailedCount: int = 0
    syntaxPassRate: float = 0.0
    docstringCoverage: float = 0.0
    functionNameMatchRate: float = 0.0
    returnAnnotationRate: float = 0.0
    instructionPairCount: int = 0


class ChartSeries(BaseModel):
    name: str
    data: list[Any]


class ChartSpec(BaseModel):
    chartId: str
    chartType: str
    title: str
    xAxis: list[str]
    series: list[ChartSeries]


class OutputFile(BaseModel):
    fileRole: str
    fileName: str
    filePath: str
    fileUrl: Optional[str] = None


class SkillExecutionLog(BaseModel):
    skillName: str
    status: str
    inputCount: int = 0
    outputCount: int = 0
    removedCount: int = 0
    durationMs: int = 0
    message: str = ""


class ExecuteResponse(BaseModel):
    taskId: int
    taskStatus: str
    metrics: Metrics
    chartSpecs: list[ChartSpec]
    outputFiles: list[OutputFile]
    executionLogs: list[SkillExecutionLog]
    summary: str
    reflectionSummary: Optional[str] = None
    qualityWarnings: Optional[list[str]] = None
    nextStepSuggestions: Optional[list[str]] = None


class ChatRequest(BaseModel):
    taskId: int
    message: str
    metrics: Optional[dict] = None
    executionLogs: Optional[list] = None
    summary: Optional[str] = None


class ChatResponse(BaseModel):
    taskId: int
    reply: str
    referMetrics: Optional[dict] = None


class RefinementAction(BaseModel):
    # rerun_with_options | clarify | compare
    actionType: str = "rerun_with_options"
    intentSummary: str
    # maximize_retention | maximize_quality | balance_retain_and_quality |
    # training_data_construction | reduce_noise | data_augmentation | compare_rounds
    optimizationGoal: Optional[str] = None
    strategyReason: Optional[list[str]] = None
    optionsDiff: dict = {}
    filterRelax: Optional[dict] = None
    expectedImpact: Optional[list[str]] = None
    riskWarnings: Optional[list[str]] = None
    # high | medium | low
    confidence: str = "high"
    clarificationNeeded: Optional[str] = None


class ParseIntentRequest(BaseModel):
    taskId: int
    userMessage: str
    currentMetrics: Optional[dict] = None
    currentOptions: Optional[dict] = None
    summary: Optional[str] = None
    reflectionSummary: Optional[str] = None
    previousRefinementAction: Optional[dict] = None


class ParseIntentResponse(BaseModel):
    taskId: int
    refinementAction: RefinementAction
