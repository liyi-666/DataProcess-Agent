# 代码生成数据预处理 Agent 系统接口与数据结构设计文档

**面向 Claude Code 协作编码的工程契约文档**

- **版本**：V1.0
- **适用范围**：前端 Vue、Spring Boot 业务后端、Python Agent 服务、MySQL、本地文件存储。
- **设计原则**：接口文档用于指导代码生成与联调，不再重复技术设计文档中的背景论证；重点明确模块边界、接口契约、数据结构、状态流转和实现约束。

---

## 1. 文档说明

本文档用于指导代码生成数据预处理 Agent 系统的接口开发与代码生成，主要面向开发者和 Claude Code。文档重点不是论证方案是否合理，而是约束各模块如何通信、数据结构如何定义、接口输入输出如何保持一致。

系统采用前后端分离和多服务协同结构。前端只调用 Spring Boot 后端；Spring Boot 负责文件接收、轻量处理状态管理、结果聚合与对外 API；Python Agent 服务负责 LangGraph 编排、skills 调用、指标分析和图表配置生成。

---

## 2. 系统模块与接口边界

| 模块 | 职责 | 不承担职责 |
|---|---|---|
| Vue 前端 | 文件上传、任务状态展示、结果展示、图表渲染、聊天面板 | 不直接调用 Python Agent，不处理数据清洗逻辑 |
| Spring Boot 后端 | 接收上传文件、临时保存文件、创建处理记录、调用 Python Agent、聚合结果并提供统一 API | 不实现 AST、去重、增强等具体预处理算法 |
| Python Agent 服务 | 接收任务上下文，基于 LangGraph 编排流程，调用 skills，返回指标、图表数据和结果文件信息 | 不直接面向前端，不负责用户系统和复杂权限 |
| MySQL | 保存任务状态、文件元数据、执行日志、分析摘要、聊天记录 | 不保存大文件二进制内容 |
| 本地文件存储 / OSS 预留 | 保存上传原始文件和处理结果文件 | 初版不实现复杂对象存储管理 |

---

## 3. 通用约定

### 3.1 统一返回格式

Spring Boot 对前端暴露的所有接口统一使用以下响应格式：

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| code | int | 0 表示成功，非 0 表示失败 |
| message | string | 接口返回说明 |
| data | object / array / null | 具体业务数据 |

### 3.2 任务状态枚举

| 状态 | 说明 |
|---|---|
| INIT | 处理请求已创建，等待执行 |
| SCHEMA_DETECTING | 正在识别文件结构和候选字段 |
| WAITING_CONFIRM | 字段映射或参数需要用户确认 |
| PREPROCESSING | 正在执行清洗、过滤、AST 抽取、去重或增强 |
| ANALYZING | 正在生成统计指标和质量分析 |
| VISUALIZING | 正在生成图表配置数据 |
| FINISHED | 处理完成，可查询结果 |
| FAILED | 处理失败，可查看错误原因 |

### 3.3 文件与样本相关枚举

| 枚举类型 | 可选值 | 说明 |
|---|---|---|
| fileType | csv / jsonl / parquet / json | 初版支持的主要文件类型 |
| fileRole | raw / cleaned / preview / badcase / stats / report | 文件在处理流程中的角色 |
| sampleUnitType | function | 当前版本核心处理单元 |
| sourceGranularity | function / file | 输入数据原始粒度，file 表示可先抽取函数级样本 |
| storageType | local / oss | 初版使用 local，oss 作为扩展预留 |

### 3.4 错误码约定

| 错误码 | 说明 | 典型场景 |
|---|---|---|
| 0 | 成功 | 接口正常返回 |
| 40001 | 参数错误 | 缺少 taskId、文件类型不支持、字段为空 |
| 40002 | 文件错误 | 文件上传失败、文件不存在、文件读取失败 |
| 40003 | 任务状态错误 | 任务已完成但重复启动、未确认字段就执行 |
| 50001 | Agent 服务调用失败 | Python Agent 不可用或返回异常 |
| 50002 | 预处理失败 | skills 执行异常、AST 解析流程异常 |
| 50003 | 系统内部错误 | 未预期异常 |

---

## 4. 前端调用 Spring Boot 接口

### 4.1 上传文件并创建处理任务

| 项目 | 内容 |
|---|---|
| 接口名称 | 上传文件并创建处理任务 |
| 请求方式 | POST |
| 接口路径 | `/api/tasks/upload` |
| Content-Type | `multipart/form-data` |
| 调用方 | Vue 前端 |
| 被调用方 | Spring Boot 后端 |
| 状态变化 | 无 -> INIT |
| 说明 | 接收用户上传的数据文件，临时保存原始文件，创建处理记录并返回 taskId |

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| file | file | 是 | 上传的数据文件，支持 csv/jsonl/parquet |
| taskName | string | 否 | 任务名称，缺省时由后端自动生成 |
| taskDescription | string | 否 | 用户对处理目标的自然语言说明 |

**响应示例**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "taskId": 1001,
    "taskStatus": "INIT",
    "fileId": 2001,
    "fileName": "dataset.parquet"
  }
}
```

### 4.2 启动处理任务

| 项目 | 内容 |
|---|---|
| 接口名称 | 启动处理任务 |
| 请求方式 | POST |
| 接口路径 | `/api/tasks/{taskId}/run` |
| Content-Type | `application/json` |
| 状态变化 | INIT -> SCHEMA_DETECTING |
| 说明 | 后端调用 Python Agent 开始 schema 识别和执行计划生成 |

**请求示例**

```json
{
  "useDefaultPlan": true,
  "options": {
    "enableDedup": true,
    "enableAstDedup": true,
    "enableAstExtract": true,
    "enableAugmentation": true,
    "enableInstructionPairs": true,
    "sampleUnitType": "function",
    "sourceGranularity": "function"
  }
}
```

**响应示例**

```json
{
  "code": 0,
  "message": "task started",
  "data": {
    "taskId": 1001,
    "taskStatus": "SCHEMA_DETECTING"
  }
}
```

### 4.3 查询任务状态

| 项目 | 内容 |
|---|---|
| 接口名称 | 查询任务状态 |
| 请求方式 | GET |
| 接口路径 | `/api/tasks/{taskId}/status` |
| 说明 | 前端轮询或手动查询当前任务状态、当前步骤、进度和是否需要用户确认 |

**响应示例：正常执行中**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "taskId": 1001,
    "taskStatus": "PREPROCESSING",
    "currentStep": "deduplicate_samples",
    "progress": 60,
    "needUserConfirm": false,
    "confirmPayload": null,
    "errorMessage": null
  }
}
```

**响应示例：等待用户确认**

```json
{
  "code": 0,
  "message": "waiting for confirmation",
  "data": {
    "taskId": 1001,
    "taskStatus": "WAITING_CONFIRM",
    "currentStep": "schema_confirm",
    "progress": 15,
    "needUserConfirm": true,
    "confirmPayload": {
      "message": "系统无法唯一确定代码字段，请选择 code 字段。",
      "candidateCodeFields": ["code", "original_string", "content"],
      "candidateDocstringFields": ["docstring", "description", "comment"],
      "candidateLanguageFields": ["language", "lang"]
    },
    "errorMessage": null
  }
}
```

### 4.4 提交字段确认

| 项目 | 内容 |
|---|---|
| 接口名称 | 提交字段确认 |
| 请求方式 | POST |
| 接口路径 | `/api/tasks/{taskId}/confirm-schema` |
| Content-Type | `application/json` |
| 状态变化 | WAITING_CONFIRM -> PREPROCESSING |
| 说明 | 当 schema 识别不确定时，由用户确认 code/docstring/language 字段后继续执行 |

**请求示例**

```json
{
  "codeField": "original_string",
  "docstringField": "docstring",
  "languageField": "language"
}
```

**响应示例**

```json
{
  "code": 0,
  "message": "schema confirmed",
  "data": {
    "taskId": 1001,
    "taskStatus": "PREPROCESSING"
  }
}
```

### 4.5 查询任务结果

| 项目 | 内容 |
|---|---|
| 接口名称 | 查询任务结果 |
| 请求方式 | GET |
| 接口路径 | `/api/tasks/{taskId}/result` |
| 说明 | 任务完成后返回摘要、指标、图表配置和结果文件列表 |

**响应示例**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "taskId": 1001,
    "taskStatus": "FINISHED",
    "summary": "本次任务完成代码清洗、AST 解析、过滤、去重和增强。",
    "metrics": {
      "rawSampleCount": 12000,
      "finalSampleCount": 8600,
      "retainRate": 0.7167,
      "syntaxPassRate": 0.93,
      "docstringCoverage": 0.78,
      "dedupRemovedCount": 1200,
      "augmentationSuccessCount": 650
    },
    "charts": [],
    "outputFiles": []
  }
}
```

### 4.6 发送聊天消息

| 项目 | 内容 |
|---|---|
| 接口名称 | 发送聊天消息 |
| 请求方式 | POST |
| 接口路径 | `/api/chat/send` |
| Content-Type | `application/json` |
| 说明 | 用户基于任务结果追问原因、指标含义或处理建议 |

**请求示例**

```json
{
  "taskId": 1001,
  "message": "为什么过滤掉了这么多样本？"
}
```

**响应示例**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "reply": "主要原因是 AST 解析失败和低质量 docstring 过滤。",
    "referMetrics": {
      "astParseFailedCount": 900,
      "lowQualityDocstringCount": 650
    }
  }
}
```

### 4.7 下载结果文件

| 项目 | 内容 |
|---|---|
| 接口名称 | 下载结果文件 |
| 请求方式 | GET |
| 接口路径 | `/api/files/{fileId}/download` |
| 说明 | 根据文件 ID 下载 cleaned、badcase、stats、preview 等结果文件 |

---

## 5. Spring Boot 调用 Python Agent 接口

### 5.1 创建处理计划 / Schema 识别

| 项目 | 内容 |
|---|---|
| 接口名称 | 创建处理计划 / Schema 识别 |
| 请求方式 | POST |
| 接口路径 | `/agent/plan` |
| 调用方 | Spring Boot |
| 被调用方 | Python Agent |
| 说明 | 根据文件路径、文件类型、用户说明和处理选项，识别候选字段并生成执行计划 |

**请求示例**

```json
{
  "taskId": 1001,
  "filePath": "data/uploads/1001/dataset.parquet",
  "fileType": "parquet",
  "taskDescription": "请完成代码生成数据预处理",
  "options": {
    "enableDedup": true,
    "enableAstDedup": true,
    "enableAstExtract": true,
    "enableAugmentation": true,
    "enableInstructionPairs": true,
    "sampleUnitType": "function",
    "sourceGranularity": "function"
  }
}
```

**响应示例**

```json
{
  "taskId": 1001,
  "taskStatus": "SCHEMA_DETECTING",
  "needUserConfirm": false,
  "confirmPayload": null,
  "detectedSchema": {
    "codeField": "original_string",
    "docstringField": "docstring",
    "languageField": "language",
    "candidateCodeFields": ["original_string", "code"],
    "candidateDocstringFields": ["docstring", "comment"]
  },
  "executionPlan": [
    "load_dataset",
    "normalize_code_text",
    "extract_function_structure",
    "filter_invalid_samples",
    "filter_low_quality_docstring",
    "deduplicate_samples",
    "rename_variables_augmentation",
    "compute_dataset_profile",
    "evaluate_data_quality",
    "generate_chart_specs"
  ]
}
```

### 5.2 执行预处理流程

| 项目 | 内容 |
|---|---|
| 接口名称 | 执行预处理流程 |
| 请求方式 | POST |
| 接口路径 | `/agent/execute` |
| 说明 | 按照 executionPlan 调用 skills，返回 metrics、chartSpecs、outputFiles 和 executionLogs |

**请求示例**

```json
{
  "taskId": 1001,
  "filePath": "data/uploads/1001/dataset.parquet",
  "fileType": "parquet",
  "schema": {
    "codeField": "original_string",
    "docstringField": "docstring",
    "languageField": "language"
  },
  "options": {
    "enableDedup": true,
    "enableAstDedup": true,
    "enableAstExtract": true,
    "enableAugmentation": true,
    "enableInstructionPairs": true,
    "sampleUnitType": "function",
    "sourceGranularity": "function"
  },
  "executionPlan": [
    "load_dataset",
    "normalize_code_text",
    "extract_function_structure",
    "filter_invalid_samples",
    "filter_low_quality_docstring",
    "deduplicate_samples",
    "rename_variables_augmentation",
    "compute_dataset_profile",
    "evaluate_data_quality",
    "generate_chart_specs"
  ]
}
```

**响应示例**

```json
{
  "taskId": 1001,
  "taskStatus": "FINISHED",
  "metrics": {
    "rawSampleCount": 12000,
    "finalSampleCount": 8600,
    "retainRate": 0.7167,
    "astParseSuccessCount": 10000,
    "astParseFailedCount": 2000,
    "dedupRemovedCount": 1200,
    "augmentationSuccessCount": 650
  },
  "chartSpecs": [],
  "outputFiles": [
    {
      "fileRole": "cleaned",
      "fileName": "processed_dataset.jsonl",
      "filePath": "data/outputs/1001/processed_dataset.jsonl",
      "fileUrl": null
    }
  ],
  "executionLogs": [
    {
      "skillName": "extract_function_structure",
      "status": "success",
      "inputCount": 12000,
      "outputCount": 10000,
      "removedCount": 2000,
      "message": "AST 解析完成"
    }
  ],
  "summary": "任务执行完成，共保留 8600 条有效样本。"
}
```

### 5.3 Agent 聊天解释接口

| 项目 | 内容 |
|---|---|
| 接口名称 | Agent 聊天解释接口 |
| 请求方式 | POST |
| 接口路径 | `/agent/chat` |
| 说明 | 基于任务指标和执行日志回答用户追问，不直接重新执行预处理 |

**请求示例**

```json
{
  "taskId": 1001,
  "message": "为什么 AST 解析失败这么多？",
  "metrics": {
    "rawSampleCount": 12000,
    "astParseFailedCount": 2000
  },
  "executionLogs": []
}
```

**响应示例**

```json
{
  "taskId": 1001,
  "reply": "AST 解析失败主要可能来自语法错误、非完整函数定义或字段识别错误。建议查看 badcases.json 中的失败样本。",
  "referMetrics": {
    "astParseFailedCount": 2000
  }
}
```

---

## 6. 核心数据结构

### 6.1 ProcessingOptions

```json
{
  "enableDedup": true,
  "enableAstDedup": true,
  "enableAstExtract": true,
  "enableAugmentation": false,
  "enableInstructionPairs": true,
  "sampleUnitType": "function",
  "sourceGranularity": "function"
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| enableDedup | boolean | 是否开启去重 |
| enableAstDedup | boolean | 是否开启 AST 去重 |
| enableAstExtract | boolean | 是否开启 AST 函数结构抽取 |
| enableAugmentation | boolean | 是否开启变量重命名增强 |
| enableInstructionPairs | boolean | 是否构造指令样本对 |
| sampleUnitType | string | 当前处理单元，初版固定为 function |
| sourceGranularity | string | 输入粒度，function 或 file |

### 6.2 DatasetSchema

```json
{
  "codeField": "original_string",
  "docstringField": "docstring",
  "languageField": "language",
  "candidateCodeFields": ["original_string", "code"],
  "candidateDocstringFields": ["docstring", "comment"],
  "candidateLanguageFields": ["language", "lang"]
}
```

### 6.3 Metrics

```json
{
  "rawSampleCount": 12000,
  "finalSampleCount": 8600,
  "retainRate": 0.7167,
  "astParseSuccessCount": 10000,
  "astParseFailedCount": 2000,
  "emptyCodeCount": 300,
  "lowQualityDocstringCount": 650,
  "dedupRemovedCount": 1200,
  "augmentationSuccessCount": 650,
  "augmentationFailedCount": 120,
  "syntaxPassRate": 0.93,
  "docstringCoverage": 0.78,
  "functionNameMatchRate": 0.85,
  "returnAnnotationRate": 0.31
}
```

### 6.4 ChartSpec

初版建议使用轻量图表结构，由前端转换为 ECharts option。

```json
{
  "chartId": "sample_count_compare",
  "chartType": "bar",
  "title": "处理前后样本数量对比",
  "xAxis": ["原始样本", "最终样本"],
  "series": [
    {
      "name": "样本数",
      "data": [12000, 8600]
    }
  ]
}
```

### 6.5 OutputFile

```json
{
  "fileRole": "cleaned",
  "fileName": "processed_dataset.jsonl",
  "filePath": "data/outputs/1001/processed_dataset.jsonl",
  "fileUrl": null
}
```

### 6.6 SkillExecutionLog

```json
{
  "skillName": "deduplicate_samples",
  "status": "success",
  "inputCount": 10000,
  "outputCount": 8800,
  "removedCount": 1200,
  "durationMs": 3200,
  "message": "去重完成"
}
```

---

## 7. 数据库表设计草案

初版仅保留项目主链路必要表，不实现登录注册和复杂权限。

### 7.1 dataset_task

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint | 任务 ID |
| task_name | varchar(128) | 任务名称 |
| task_description | text | 任务说明 |
| task_status | varchar(32) | 任务状态 |
| current_step | varchar(64) | 当前步骤 |
| progress | int | 进度百分比 |
| need_user_confirm | tinyint | 是否需要用户确认 |
| confirm_payload | json | 待确认内容 |
| error_message | text | 错误信息 |
| create_time / update_time | datetime | 创建和更新时间 |

### 7.2 dataset_file

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint | 文件 ID |
| task_id | bigint | 所属任务 ID |
| file_name | varchar(255) | 文件名 |
| file_type | varchar(32) | 文件类型 |
| file_role | varchar(32) | raw/cleaned/preview/badcase/stats/report |
| storage_type | varchar(16) | local/oss |
| file_path | varchar(512) | 本地路径或对象键 |
| file_url | varchar(1024) | 访问地址，可为空 |
| file_size | bigint | 文件大小 |

### 7.3 skill_execution_log

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint | 日志 ID |
| task_id | bigint | 所属任务 ID |
| skill_name | varchar(128) | skill 名称 |
| execution_order | int | 执行顺序 |
| execution_status | varchar(32) | running/success/failed/skipped |
| input_summary | text | 输入摘要 |
| output_summary | text | 输出摘要 |
| execution_time_ms | bigint | 执行耗时 |
| error_message | text | 错误信息 |

### 7.4 analysis_report

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint | 报告 ID |
| task_id | bigint | 所属任务 ID |
| report_json | json | 结构化分析结果 |
| summary_text | text | 文本摘要 |
| create_time | datetime | 创建时间 |

### 7.5 chat_message

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint | 消息 ID |
| task_id | bigint | 关联任务 ID |
| role | varchar(16) | user/assistant/system |
| content | mediumtext | 消息内容 |
| create_time | datetime | 创建时间 |

---

## 8. 文件存储约定

```text
data/
  uploads/
    {taskId}/
      原始上传文件
  outputs/
    {taskId}/
      processed_dataset.jsonl
      preview.json
      badcases.json
      stats.json
```

上传文件采用临时保存机制，用于任务执行、失败重试和结果导出。

初版使用本地文件系统，不实现 OSS；表结构中预留 storageType、fileUrl 等字段。

大文件不写入 MySQL，MySQL 只保存路径、角色、大小等元数据。

---

## 9. Python Agent Skills 约定

| Skill | 职责 |
|---|---|
| detect_dataset_schema | 识别文件类型、字段名和候选 code/docstring/language 字段 |
| load_dataset | 读取 csv/jsonl/parquet 并转为统一数据结构 |
| normalize_code_text | 执行代码与文档清洗 |
| extract_function_structure | 基于 AST 提取函数名、参数、返回注解和 docstring |
| filter_invalid_samples | 执行空值、长度、语法等过滤 |
| filter_low_quality_docstring | 过滤低质量文档字符串 |
| deduplicate_samples | 执行精确去重和 AST 去重 |
| rename_variables_augmentation | 执行变量重命名增强 |
| build_instruction_pairs | 构造 docstring -> code 等指令样本 |
| compute_dataset_profile | 生成数据画像统计 |
| evaluate_data_quality | 生成质量指标 |
| generate_chart_specs | 生成前端图表配置数据 |

实现建议：skills 先作为 Python 内部模块实现，通过 Skill Registry 按名称调用，不在初版实现动态插件系统。

---

## 10. Claude Code 实现约束

1. 不要实现登录注册系统，默认单用户场景。
2. 不要实现复杂权限系统。
3. 不要实现 OSS，文件先存本地；仅保留字段预留。
4. Spring Boot 不实现具体数据预处理算法，只负责文件接收、状态管理、结果聚合和调用 Python Agent。
5. Python Agent 负责 LangGraph 编排和 skills 调用。
6. Vue 前端不直接调用 Python Agent，只调用 Spring Boot。
7. 图表由前端渲染，后端只返回 ChartSpec 数据。
8. 当前版本只重点支持 Python 函数级代码数据。
9. 允许输入文件级代码，但处理目标统一抽取为函数级样本。
10. 所有接口先实现可跑通版本，异常处理保持简洁。

---

## 11. 建议实现顺序

| 阶段 | 目标 | 优先实现内容 |
|---|---|---|
| 第一阶段 | 跑通基础后端 | Spring Boot 项目、MySQL 表、文件上传、任务创建、状态查询 |
| 第二阶段 | 跑通 Agent 主链路 | `/agent/plan`、`/agent/execute`、schema 识别、数据加载、清洗、AST 抽取 |
| 第三阶段 | 生成结果与图表 | metrics、chartSpecs、outputFiles、结果查询接口、Vue 图表展示 |
| 第四阶段 | 增强能力 | AST 去重、变量重命名增强、坏样本预览、聊天解释 |
| 第五阶段 | 体验优化 | 字段确认、日志展示、下载结果文件 |

---

## 12. 总结

本文档定义了代码生成数据预处理 Agent 系统的接口契约和核心数据结构。开发时应严格保持模块边界：前端负责交互与渲染，Spring Boot 负责请求接入和状态管理，Python Agent 负责预处理编排与 skills 执行，MySQL 负责元数据持久化，文件系统负责原始文件和结果文件存储。Claude Code 编码时应优先实现主链路，避免生成与当前版本无关的复杂功能。
