package com.dataprocess.agent.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.dataprocess.agent.client.AgentClient;
import com.dataprocess.agent.dto.MetricsDiffResponse;
import com.dataprocess.agent.dto.RefineRunRequest;
import com.dataprocess.agent.dto.RefinementActionDto;
import com.dataprocess.agent.dto.ConfirmSchemaRequest;
import com.dataprocess.agent.dto.RunTaskRequest;
import com.dataprocess.agent.dto.TaskResultResponse;
import com.dataprocess.agent.dto.TaskStatusResponse;
import com.dataprocess.agent.entity.*;
import com.dataprocess.agent.repository.*;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.io.File;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.*;
import java.util.concurrent.CompletableFuture;

@Service
@Slf4j
@RequiredArgsConstructor
public class TaskService {

    private final DatasetTaskRepository taskRepo;
    private final DatasetFileRepository fileRepo;
    private final SkillExecutionLogRepository skillLogRepo;
    private final AnalysisReportRepository reportRepo;
    private final AgentClient agentClient;
    private final ObjectMapper objectMapper;
    private final TaskProgressService taskProgressService;

    @Value("${storage.upload-dir:data/uploads}")
    private String uploadDir;

    @Value("${storage.output-dir:data/outputs}")
    private String outputDir;

    @Value("${server.port:8081}")
    private String serverPort;

    public Map<String, Object> upload(MultipartFile file, String taskName, String taskDescription) {
        DatasetTask task = new DatasetTask();
        task.setTaskName(taskName != null ? taskName : "task_" + System.currentTimeMillis());
        task.setTaskDescription(taskDescription);
        task.setTaskStatus("INIT");
        task.setProgress(0);
        task.setNeedUserConfirm(false);
        taskRepo.insert(task);

        Long taskId = task.getId();
        Path dirPath = Paths.get(uploadDir, String.valueOf(taskId)).toAbsolutePath();
        dirPath.toFile().mkdirs();

        String originalName = file.getOriginalFilename();
        Path savePath = dirPath.resolve(originalName);
        try {
            Files.copy(file.getInputStream(), savePath, java.nio.file.StandardCopyOption.REPLACE_EXISTING);
        } catch (Exception e) {
            throw new RuntimeException("文件保存失败: " + e.getMessage(), e);
        }

        DatasetFile df = new DatasetFile();
        df.setTaskId(taskId);
        df.setFileName(originalName);
        df.setFileType(getExtension(originalName));
        df.setFileRole("raw");
        df.setStorageType("local");
        df.setFilePath(savePath.toString());
        df.setFileSize(file.getSize());
        fileRepo.insert(df);

        Map<String, Object> result = new HashMap<>();
        result.put("taskId", taskId);
        result.put("taskStatus", "INIT");
        result.put("fileId", df.getId());
        result.put("fileName", originalName);
        return result;
    }

    public Map<String, Object> planTask(Long taskId) {
        DatasetTask task = taskRepo.selectById(taskId);
        if (task == null) throw new RuntimeException("任务不存在: " + taskId);

        DatasetFile rawFile = fileRepo.selectOne(
                new LambdaQueryWrapper<DatasetFile>()
                        .eq(DatasetFile::getTaskId, taskId)
                        .eq(DatasetFile::getFileRole, "raw")
                        .last("LIMIT 1")
        );
        if (rawFile == null) throw new RuntimeException("未找到上传文件");

        task.setTaskStatus("PLANNING");
        task.setProgress(5);
        task.setCurrentStep("planning");
        taskRepo.updateById(task);

        Map<String, Object> planBody = new HashMap<>();
        planBody.put("taskId", taskId);
        planBody.put("filePath", rawFile.getFilePath());
        planBody.put("fileType", rawFile.getFileType());
        planBody.put("taskDescription", task.getTaskDescription());
        planBody.put("options", new HashMap<>());

        Map<String, Object> planResult = agentClient.plan(planBody);

        // Build planObservations: display fields + internal fields (prefixed _)
        Map<String, Object> planObs = new HashMap<>();
        planObs.put("observedDatasetTraits", planResult.get("observedDatasetTraits"));
        planObs.put("recommendedMode", planResult.get("recommendedMode"));
        planObs.put("riskWarnings", planResult.get("riskWarnings"));
        planObs.put("recommendationReason", planResult.get("recommendationReason"));
        planObs.put("recommendedExecutionPlan", planResult.get("recommendedExecutionPlan"));
        planObs.put("recommendedOptions", planResult.get("recommendedOptions"));
        planObs.put("_executionPlan", planResult.get("executionPlan"));
        planObs.put("_detectedSchema", planResult.get("detectedSchema"));
        planObs.put("_needUserConfirm", planResult.get("needUserConfirm"));
        planObs.put("_confirmPayload", planResult.get("confirmPayload"));

        task.setPlanObservations(planObs);
        task.setTaskStatus("PLAN_READY");
        task.setProgress(10);
        taskRepo.updateById(task);

        Map<String, Object> resp = new HashMap<>();
        resp.put("taskId", taskId);
        resp.put("taskStatus", "PLAN_READY");
        resp.put("observedDatasetTraits", planResult.get("observedDatasetTraits"));
        resp.put("recommendedMode", planResult.get("recommendedMode"));
        resp.put("riskWarnings", planResult.get("riskWarnings"));
        resp.put("recommendationReason", planResult.get("recommendationReason"));
        resp.put("recommendedExecutionPlan", planResult.get("recommendedExecutionPlan"));
        resp.put("recommendedOptions", planResult.get("recommendedOptions"));
        resp.put("needUserConfirm", planResult.get("needUserConfirm"));
        resp.put("confirmPayload", planResult.get("confirmPayload"));
        return resp;
    }

    public Map<String, Object> runTask(Long taskId, RunTaskRequest req) {
        DatasetTask task = taskRepo.selectById(taskId);
        if (task == null) throw new RuntimeException("任务不存在: " + taskId);

        String currentStatus = task.getTaskStatus();
        if ("PREPROCESSING".equals(currentStatus) || "FINISHED".equals(currentStatus)) {
            log.warn("[runTask] taskId={} rejected: status={}", taskId, currentStatus);
            Map<String, Object> resp = new HashMap<>();
            resp.put("taskId", taskId);
            resp.put("taskStatus", currentStatus);
            resp.put("message", "任务已在执行中或已完成，不允许重复启动");
            return resp;
        }

        DatasetFile rawFile = fileRepo.selectOne(
                new LambdaQueryWrapper<DatasetFile>()
                        .eq(DatasetFile::getTaskId, taskId)
                        .eq(DatasetFile::getFileRole, "raw")
                        .last("LIMIT 1")
        );
        if (rawFile == null) throw new RuntimeException("未找到上传文件");

        RunTaskRequest.ProcessingOptions opts = req.getOptions() != null ? req.getOptions() : new RunTaskRequest.ProcessingOptions();

        // Reuse saved plan if already done
        if ("PLAN_READY".equals(task.getTaskStatus()) && task.getPlanObservations() != null) {
            return runWithSavedPlan(task, rawFile, opts);
        }

        // Original flow: plan then execute
        task.setTaskStatus("SCHEMA_DETECTING");
        task.setProgress(5);
        taskRepo.updateById(task);

        Map<String, Object> optsMap = objectMapper.convertValue(opts, Map.class);
        Map<String, Object> planBody = new HashMap<>();
        planBody.put("taskId", taskId);
        planBody.put("filePath", rawFile.getFilePath());
        planBody.put("fileType", rawFile.getFileType());
        planBody.put("taskDescription", task.getTaskDescription());
        planBody.put("options", optsMap);

        Map<String, Object> planResult = agentClient.plan(planBody);

        Map<String, Object> planObs = new HashMap<>();
        planObs.put("observedDatasetTraits", planResult.get("observedDatasetTraits"));
        planObs.put("recommendedMode", planResult.get("recommendedMode"));
        planObs.put("riskWarnings", planResult.get("riskWarnings"));
        planObs.put("recommendationReason", planResult.get("recommendationReason"));
        planObs.put("_detectedSchema", planResult.get("detectedSchema"));
        planObs.put("_executionPlan", planResult.get("executionPlan"));
        task.setPlanObservations(planObs);

        Boolean needConfirm = (Boolean) planResult.getOrDefault("needUserConfirm", false);
        if (Boolean.TRUE.equals(needConfirm)) {
            task.setTaskStatus("WAITING_CONFIRM");
            task.setNeedUserConfirm(true);
            task.setCurrentStep("schema_confirm");
            task.setProgress(15);

            Map<String, Object> payload = new HashMap<>();
            Object confirmPayload = planResult.get("confirmPayload");
            if (confirmPayload instanceof Map) {
                payload.putAll((Map<String, Object>) confirmPayload);
            }
            payload.put("_executionPlan", planResult.get("executionPlan"));
            payload.put("_filePath", rawFile.getFilePath());
            payload.put("_fileType", rawFile.getFileType());
            payload.put("_options", opts);
            task.setConfirmPayload(payload);
            taskRepo.updateById(task);

            Map<String, Object> resp = new HashMap<>();
            resp.put("taskId", taskId);
            resp.put("taskStatus", "WAITING_CONFIRM");
            return resp;
        }

        return doExecute(task, rawFile.getFilePath(), rawFile.getFileType(),
                planResult.get("detectedSchema"), trimPlanByOptions(planResult.get("executionPlan"), opts), opts);
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> runWithSavedPlan(DatasetTask task, DatasetFile rawFile, RunTaskRequest.ProcessingOptions opts) {
        Object rawPlan = task.getPlanObservations();
        Map<String, Object> savedPlan;
        if (rawPlan instanceof Map) {
            savedPlan = (Map<String, Object>) rawPlan;
        } else if (rawPlan instanceof String) {
            try {
                savedPlan = objectMapper.readValue((String) rawPlan, Map.class);
            } catch (Exception e) {
                throw new RuntimeException("planObservations 解析失败: " + e.getMessage(), e);
            }
        } else {
            throw new RuntimeException("planObservations 数据异常，无法解析");
        }

        Boolean needConfirm = (Boolean) savedPlan.getOrDefault("_needUserConfirm", false);
        Object detectedSchema = savedPlan.get("_detectedSchema");
        Object executionPlan = trimPlanByOptions(savedPlan.get("_executionPlan"), opts);

        // Keep display fields + internal schema/plan fields needed for future refineRun
        Map<String, Object> planObs = new HashMap<>();
        planObs.put("observedDatasetTraits", savedPlan.get("observedDatasetTraits"));
        planObs.put("recommendedMode", savedPlan.get("recommendedMode"));
        planObs.put("riskWarnings", savedPlan.get("riskWarnings"));
        planObs.put("recommendationReason", savedPlan.get("recommendationReason"));
        planObs.put("recommendedExecutionPlan", savedPlan.get("recommendedExecutionPlan"));
        planObs.put("_detectedSchema", detectedSchema);
        planObs.put("_executionPlan", executionPlan);
        task.setPlanObservations(planObs);

        if (Boolean.TRUE.equals(needConfirm)) {
            task.setTaskStatus("WAITING_CONFIRM");
            task.setNeedUserConfirm(true);
            task.setCurrentStep("schema_confirm");
            task.setProgress(15);

            Map<String, Object> payload = new HashMap<>();
            Object confirmPayload = savedPlan.get("_confirmPayload");
            if (confirmPayload instanceof Map) {
                payload.putAll((Map<String, Object>) confirmPayload);
            }
            payload.put("_executionPlan", executionPlan);
            payload.put("_filePath", rawFile.getFilePath());
            payload.put("_fileType", rawFile.getFileType());
            payload.put("_options", opts);
            task.setConfirmPayload(payload);
            taskRepo.updateById(task);

            Map<String, Object> resp = new HashMap<>();
            resp.put("taskId", task.getId());
            resp.put("taskStatus", "WAITING_CONFIRM");
            return resp;
        }

        return doExecute(task, rawFile.getFilePath(), rawFile.getFileType(), detectedSchema, executionPlan, opts);
    }

    public Map<String, Object> confirmSchema(Long taskId, ConfirmSchemaRequest req) {
        DatasetTask task = taskRepo.selectById(taskId);
        if (task == null) throw new RuntimeException("任务不存在: " + taskId);

        if (!"WAITING_CONFIRM".equals(task.getTaskStatus())) {
            log.warn("[confirmSchema] taskId={} rejected: status={}", taskId, task.getTaskStatus());
            Map<String, Object> resp = new HashMap<>();
            resp.put("taskId", taskId);
            resp.put("taskStatus", task.getTaskStatus());
            resp.put("message", "任务当前状态不允许确认: " + task.getTaskStatus());
            return resp;
        }

        DatasetFile rawFile = fileRepo.selectOne(
                new LambdaQueryWrapper<DatasetFile>()
                        .eq(DatasetFile::getTaskId, taskId)
                        .eq(DatasetFile::getFileRole, "raw")
                        .last("LIMIT 1")
        );

        @SuppressWarnings("unchecked")
        Map<String, Object> savedPayload;
        Object rawConfirmPayload = task.getConfirmPayload();
        if (rawConfirmPayload instanceof Map) {
            savedPayload = (Map<String, Object>) rawConfirmPayload;
        } else if (rawConfirmPayload instanceof String) {
            try {
                savedPayload = objectMapper.readValue((String) rawConfirmPayload, Map.class);
            } catch (Exception e) {
                log.warn("[confirmSchema] taskId={} failed to parse confirmPayload: {}", taskId, e.getMessage());
                savedPayload = new HashMap<>();
            }
        } else {
            savedPayload = new HashMap<>();
        }

        Map<String, Object> schema = new HashMap<>();
        schema.put("codeField", req.getCodeField());
        schema.put("docstringField", req.getDocstringField());
        schema.put("languageField", req.getLanguageField());

        // 将用户确认的 schema 回写到 planObservations，供后续 refineRun 使用
        Object rawPlanObs = task.getPlanObservations();
        @SuppressWarnings("unchecked")
        Map<String, Object> planObs;
        if (rawPlanObs instanceof Map) {
            planObs = new HashMap<>((Map<String, Object>) rawPlanObs);
        } else if (rawPlanObs instanceof String) {
            try {
                planObs = objectMapper.readValue((String) rawPlanObs, Map.class);
            } catch (Exception e) {
                planObs = new HashMap<>();
            }
        } else {
            planObs = new HashMap<>();
        }
        planObs.put("_detectedSchema", schema);
        task.setPlanObservations(planObs);
        taskRepo.updateById(task);

        Object executionPlan = savedPayload.get("_executionPlan");
        String filePath = savedPayload.containsKey("_filePath") ? (String) savedPayload.get("_filePath") : rawFile.getFilePath();
        String fileType = savedPayload.containsKey("_fileType") ? (String) savedPayload.get("_fileType") : rawFile.getFileType();
        Object options = savedPayload.getOrDefault("_options", new RunTaskRequest.ProcessingOptions());

        log.info("[confirmSchema] taskId={} raw _options from savedPayload: {}", taskId, options);

        RunTaskRequest.ProcessingOptions typedOpts = options instanceof RunTaskRequest.ProcessingOptions
                ? (RunTaskRequest.ProcessingOptions) options
                : objectMapper.convertValue(options, RunTaskRequest.ProcessingOptions.class);

        log.info("[confirmSchema] taskId={} typedOpts.enableInstructionPairs={}", taskId, typedOpts.getEnableInstructionPairs());

        executionPlan = trimPlanByOptions(executionPlan, typedOpts);

        // 若 executionPlan 仍为 null（savedPayload 中未存储），用默认计划裁剪后兜底
        if (executionPlan == null) {
            List<String> defaultPlan = new ArrayList<>(Arrays.asList(
                "load_dataset", "normalize_code_text", "extract_function_structure",
                "filter_invalid_samples", "filter_low_quality_docstring", "deduplicate_samples",
                "rename_variables_augmentation", "build_instruction_pairs",
                "compute_dataset_profile", "evaluate_data_quality", "generate_chart_specs"
            ));
            executionPlan = trimPlanByOptions(defaultPlan, typedOpts);
        }

        log.info("[confirmSchema] taskId={} trimmed executionPlan={}", taskId, executionPlan);

        return doExecute(task, filePath, fileType, schema, executionPlan, typedOpts);
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> doExecute(DatasetTask task, String filePath, String fileType,
                                           Object schema, Object executionPlan, Object options) {
        Long taskId = task.getId();
        task.setTaskStatus("PREPROCESSING");
        task.setProgress(20);
        task.setNeedUserConfirm(false);

        // Persist the actual options used so refineRun can inherit them
        Object rawPlanObs = task.getPlanObservations();
        Map<String, Object> planObs;
        if (rawPlanObs instanceof Map) {
            planObs = new HashMap<>((Map<String, Object>) rawPlanObs);
        } else if (rawPlanObs instanceof String) {
            try { planObs = objectMapper.readValue((String) rawPlanObs, Map.class); }
            catch (Exception e) { planObs = new HashMap<>(); }
        } else {
            planObs = new HashMap<>();
        }
        planObs.put("_options", options instanceof Map ? options : objectMapper.convertValue(options, Map.class));
        task.setPlanObservations(planObs);

        taskRepo.updateById(task);

        Map<String, Object> execBody = new HashMap<>();
        execBody.put("taskId", taskId);
        execBody.put("filePath", filePath);
        execBody.put("fileType", fileType);
        execBody.put("schema", schema);
        execBody.put("options", options instanceof Map ? options : objectMapper.convertValue(options, Map.class));
        execBody.put("executionPlan", executionPlan);
        execBody.put("callbackUrl", "http://localhost:" + serverPort + "/api/tasks/" + taskId + "/progress/callback");

        CompletableFuture.runAsync(() -> {
            try {
                Map<String, Object> execResult = agentClient.execute(execBody);

                DatasetTask t = taskRepo.selectById(taskId);
                t.setTaskStatus("FINISHED");
                t.setProgress(100);
                t.setCurrentStep("done");
                taskRepo.updateById(t);

                // 保存 skill 执行日志
                List<Map<String, Object>> logs = (List<Map<String, Object>>) execResult.getOrDefault("executionLogs", List.of());
                for (int i = 0; i < logs.size(); i++) {
                    Map<String, Object> log = logs.get(i);
                    SkillExecutionLog entity = new SkillExecutionLog();
                    entity.setTaskId(taskId);
                    entity.setSkillName((String) log.get("skillName"));
                    entity.setExecutionOrder(i);
                    entity.setExecutionStatus((String) log.getOrDefault("status", "success"));
                    entity.setInputSummary("inputCount=" + log.getOrDefault("inputCount", 0));
                    entity.setOutputSummary("outputCount=" + log.getOrDefault("outputCount", 0));
                    Object dur = log.get("durationMs");
                    entity.setExecutionTimeMs(dur instanceof Number ? ((Number) dur).longValue() : 0L);
                    entity.setErrorMessage(null);
                    skillLogRepo.insert(entity);
                }

                // 保存分析报告
                AnalysisReport report = new AnalysisReport();
                report.setTaskId(taskId);
                report.setReportJson(execResult);
                report.setSummaryText((String) execResult.getOrDefault("summary", ""));
                reportRepo.insert(report);

                // 保存输出文件元数据
                List<Map<String, Object>> outputFiles = (List<Map<String, Object>>) execResult.getOrDefault("outputFiles", List.of());
                for (Map<String, Object> of : outputFiles) {
                    DatasetFile df = new DatasetFile();
                    df.setTaskId(taskId);
                    df.setFileName((String) of.get("fileName"));
                    df.setFileRole((String) of.get("fileRole"));
                    df.setFilePath((String) of.get("filePath"));
                    df.setStorageType("local");
                    df.setFileUrl((String) of.get("fileUrl"));
                    fileRepo.insert(df);
                }
                taskProgressService.complete(taskId);
            } catch (Exception e) {
                DatasetTask t = taskRepo.selectById(taskId);
                t.setTaskStatus("FAILED");
                t.setErrorMessage(e.getMessage());
                taskRepo.updateById(t);
                taskProgressService.publishError(taskId, e.getMessage());
            }
        });

        Map<String, Object> resp = new HashMap<>();
        resp.put("taskId", taskId);
        resp.put("taskStatus", "PREPROCESSING");
        return resp;
    }

    public TaskStatusResponse getStatus(Long taskId) {
        DatasetTask task = taskRepo.selectById(taskId);
        if (task == null) throw new RuntimeException("任务不存在: " + taskId);

        TaskStatusResponse resp = new TaskStatusResponse();
        resp.setTaskId(task.getId());
        resp.setTaskStatus(task.getTaskStatus());
        resp.setCurrentStep(task.getCurrentStep());
        resp.setProgress(task.getProgress());
        resp.setNeedUserConfirm(task.getNeedUserConfirm());

        // 确保 confirmPayload 是 Map 对象，不是 JSON 字符串
        Object payload = task.getConfirmPayload();
        if (task.getNeedUserConfirm() != null && task.getNeedUserConfirm() && payload != null) {
            if (payload instanceof String) {
                try {
                    payload = objectMapper.readValue((String) payload, Map.class);
                } catch (Exception e) {
                    // 如果解析失败，保持原样
                }
            }
            resp.setConfirmPayload(payload);
        } else {
            resp.setConfirmPayload(null);
        }

        Object planObs = task.getPlanObservations();
        if (planObs instanceof String) {
            try {
                planObs = objectMapper.readValue((String) planObs, Map.class);
            } catch (Exception e) {
                // 保持原样
            }
        }
        resp.setPlanObservations(planObs);
        resp.setErrorMessage(task.getErrorMessage());
        resp.setParentTaskId(task.getParentTaskId());
        resp.setRoundIndex(task.getRoundIndex());
        return resp;
    }

    @SuppressWarnings("unchecked")
    public TaskResultResponse getResult(Long taskId) {
        DatasetTask task = taskRepo.selectById(taskId);
        if (task == null) throw new RuntimeException("任务不存在: " + taskId);

        AnalysisReport report = reportRepo.selectOne(
                new LambdaQueryWrapper<AnalysisReport>()
                        .eq(AnalysisReport::getTaskId, taskId)
                        .last("LIMIT 1")
        );

        List<DatasetFile> outputFiles = fileRepo.selectList(
                new LambdaQueryWrapper<DatasetFile>()
                        .eq(DatasetFile::getTaskId, taskId)
                        .ne(DatasetFile::getFileRole, "raw")
        );

        List<SkillExecutionLog> executionLogs = skillLogRepo.selectList(
                new LambdaQueryWrapper<SkillExecutionLog>()
                        .eq(SkillExecutionLog::getTaskId, taskId)
                        .orderByAsc(SkillExecutionLog::getExecutionOrder)
        );

        TaskResultResponse resp = new TaskResultResponse();
        resp.setTaskId(taskId);
        resp.setTaskStatus(task.getTaskStatus());

        if (report != null) {
            resp.setSummary(report.getSummaryText());
            if (report.getReportJson() instanceof Map) {
                Map<String, Object> rj = (Map<String, Object>) report.getReportJson();
                resp.setMetrics(rj.get("metrics"));
                Object charts = rj.get("chartSpecs");
                resp.setCharts(charts instanceof List ? (List<Object>) charts : List.of());
                resp.setReflectionSummary((String) rj.get("reflectionSummary"));
                Object qw = rj.get("qualityWarnings");
                if (qw instanceof List) resp.setQualityWarnings((List<String>) qw);
                Object ns = rj.get("nextStepSuggestions");
                if (ns instanceof List) resp.setNextStepSuggestions((List<String>) ns);
            }
        }

        List<Object> files = new ArrayList<>();
        for (DatasetFile f : outputFiles) {
            Map<String, Object> fm = new HashMap<>();
            fm.put("fileId", f.getId());
            fm.put("fileRole", f.getFileRole());
            fm.put("fileName", f.getFileName());
            fm.put("filePath", f.getFilePath());
            fm.put("fileUrl", f.getFileUrl());
            files.add(fm);
        }
        resp.setOutputFiles(files);

        List<Object> logs = new ArrayList<>();
        for (SkillExecutionLog log : executionLogs) {
            Map<String, Object> lm = new HashMap<>();
            lm.put("skillName", log.getSkillName());
            lm.put("status", log.getExecutionStatus());
            // 从 inputSummary 和 outputSummary 中提取数字
            lm.put("inputCount", extractCount(log.getInputSummary(), "inputCount="));
            lm.put("outputCount", extractCount(log.getOutputSummary(), "outputCount="));
            lm.put("removedCount", 0); // 可以从 inputCount - outputCount 计算
            lm.put("durationMs", log.getExecutionTimeMs());
            lm.put("message", log.getErrorMessage() != null ? log.getErrorMessage() : "");
            logs.add(lm);
        }
        resp.setExecutionLogs(logs);

        Object planObs = task.getPlanObservations();
        if (planObs instanceof String) {
            try { planObs = objectMapper.readValue((String) planObs, Map.class); } catch (Exception e) { planObs = null; }
        }
        if (planObs instanceof Map) {
            resp.setOptions(((Map<?, ?>) planObs).get("_options"));
        }

        return resp;
    }

    public DatasetFile getFileById(Long fileId) {
        return fileRepo.selectById(fileId);
    }

    /**
     * 根据用户最终选择的 options 裁剪 executionPlan，
     * 移除因选项关闭而不应执行的可选 skill。
     */
    @SuppressWarnings("unchecked")
    private Object trimPlanByOptions(Object executionPlan, RunTaskRequest.ProcessingOptions opts) {
        if (!(executionPlan instanceof List)) return executionPlan;
        List<String> plan = new ArrayList<>((List<String>) executionPlan);
        if (opts == null) return plan;
        if (!Boolean.TRUE.equals(opts.getEnableAugmentation())) {
            plan.remove("rename_variables_augmentation");
        }
        if (!Boolean.TRUE.equals(opts.getEnableInstructionPairs())) {
            plan.remove("build_instruction_pairs");
        }
        return plan;
    }

    private String getExtension(String fileName) {
        if (fileName == null) return "unknown";
        int dot = fileName.lastIndexOf('.');
        return dot >= 0 ? fileName.substring(dot + 1).toLowerCase() : "unknown";
    }

    private int extractCount(String summary, String prefix) {
        if (summary == null || !summary.contains(prefix)) return 0;
        try {
            String numStr = summary.substring(summary.indexOf(prefix) + prefix.length()).trim();
            int endIdx = 0;
            while (endIdx < numStr.length() && Character.isDigit(numStr.charAt(endIdx))) {
                endIdx++;
            }
            return endIdx > 0 ? Integer.parseInt(numStr.substring(0, endIdx)) : 0;
        } catch (Exception e) {
            return 0;
        }
    }

    // ─── 多轮协作式二次处理 ───────────────────────────────────────────────────

    @SuppressWarnings("unchecked")
    public Map<String, Object> parseIntent(Long taskId, Map<String, Object> req) {
        DatasetTask task = taskRepo.selectById(taskId);
        if (task == null) throw new RuntimeException("任务不存在: " + taskId);

        // 从报告中取当前 metrics
        AnalysisReport report = reportRepo.selectOne(
                new LambdaQueryWrapper<AnalysisReport>()
                        .eq(AnalysisReport::getTaskId, taskId)
                        .last("LIMIT 1")
        );
        Object currentMetrics = null;
        if (report != null && report.getReportJson() instanceof Map) {
            currentMetrics = ((Map<String, Object>) report.getReportJson()).get("metrics");
        }

        Map<String, Object> body = new HashMap<>();
        body.put("taskId", taskId);
        body.put("userMessage", req.get("userMessage"));
        body.put("currentMetrics", currentMetrics);
        body.put("currentOptions", req.get("currentOptions"));
        body.put("summary", req.get("summary"));
        body.put("reflectionSummary", req.get("reflectionSummary"));

        // 传入上一轮的 refinementAction，让 Agent 理解相对表达（"再放宽一点"等）
        String prevActionJson = task.getRefinementAction();
        if (prevActionJson != null && !prevActionJson.isBlank()) {
            try {
                body.put("previousRefinementAction", objectMapper.readValue(prevActionJson, Map.class));
            } catch (Exception ignored) {}
        }

        Map<String, Object> result = agentClient.parseIntent(body);
        return result;
    }

    @SuppressWarnings("unchecked")
    public Map<String, Object> refineRun(Long taskId, RefineRunRequest req) {
        DatasetTask parent = taskRepo.selectById(taskId);
        if (parent == null) throw new RuntimeException("父任务不存在: " + taskId);

        // 找到父任务的原始文件
        DatasetFile rawFile = fileRepo.selectOne(
                new LambdaQueryWrapper<DatasetFile>()
                        .eq(DatasetFile::getTaskId, taskId)
                        .eq(DatasetFile::getFileRole, "raw")
                        .last("LIMIT 1")
        );
        if (rawFile == null) throw new RuntimeException("父任务未找到原始文件");

        // 创建派生任务
        int newRound = (parent.getRoundIndex() != null ? parent.getRoundIndex() : 0) + 1;
        DatasetTask derived = new DatasetTask();
        derived.setTaskName((parent.getTaskName() != null ? parent.getTaskName() : "task") + "_round" + newRound);
        derived.setTaskDescription(parent.getTaskDescription());
        derived.setTaskStatus("INIT");
        derived.setProgress(0);
        derived.setNeedUserConfirm(false);
        derived.setParentTaskId(taskId);
        derived.setRoundIndex(newRound);

        RefinementActionDto action = req.getRefinementAction();
        if (action != null) {
            try {
                derived.setRefinementAction(objectMapper.writeValueAsString(action));
            } catch (Exception e) {
                // ignore serialization failure
            }
        }
        taskRepo.insert(derived);

        // 复制原始文件记录到派生任务
        DatasetFile derivedFile = new DatasetFile();
        derivedFile.setTaskId(derived.getId());
        derivedFile.setFileName(rawFile.getFileName());
        derivedFile.setFileType(rawFile.getFileType());
        derivedFile.setFileRole("raw");
        derivedFile.setStorageType(rawFile.getStorageType());
        derivedFile.setFilePath(rawFile.getFilePath());
        derivedFile.setFileSize(rawFile.getFileSize());
        fileRepo.insert(derivedFile);

        // 合并父任务 planObservations 中的 schema 和 executionPlan
        Object parentPlanObs = parent.getPlanObservations();
        Map<String, Object> savedPlan = new HashMap<>();
        if (parentPlanObs instanceof Map) {
            savedPlan = (Map<String, Object>) parentPlanObs;
        } else if (parentPlanObs instanceof String) {
            try {
                savedPlan = objectMapper.readValue((String) parentPlanObs, Map.class);
            } catch (Exception ignored) {}
        }

        Object detectedSchema = savedPlan.get("_detectedSchema");
        Object executionPlan = savedPlan.get("_executionPlan");

        // 构建合并后的 options：继承父任务实际使用的 options，再用 optionsDiff 覆盖
        Map<String, Object> mergedOptions = new HashMap<>();
        // 系统默认值（兜底）
        mergedOptions.put("enableDedup", true);
        mergedOptions.put("enableAstDedup", true);
        mergedOptions.put("enableAstExtract", true);
        mergedOptions.put("enableAugmentation", false);
        mergedOptions.put("enableInstructionPairs", false);
        mergedOptions.put("sampleUnitType", "function");
        mergedOptions.put("sourceGranularity", "function");

        // 用父任务实际 options 覆盖默认值
        Object parentOptions = savedPlan.get("_options");
        if (parentOptions instanceof Map) {
            mergedOptions.putAll((Map<String, Object>) parentOptions);
        }

        if (action != null && action.getOptionsDiff() != null) {
            mergedOptions.putAll(action.getOptionsDiff());
        }

        // filterRelax 中的阈值直接合并进 options，Python 端按字段名读取
        if (action != null && action.getFilterRelax() != null) {
            mergedOptions.putAll(action.getFilterRelax());
        }

        // Fallback: schema missing (task created before persistence fix) — re-run plan
        if (detectedSchema == null) {
            Map<String, Object> planBody = new HashMap<>();
            planBody.put("taskId", derived.getId());  // use derived task ID to avoid stale checkpoint
            planBody.put("filePath", rawFile.getFilePath());
            planBody.put("fileType", rawFile.getFileType());
            planBody.put("taskDescription", parent.getTaskDescription());
            planBody.put("options", mergedOptions);
            Map<String, Object> planResult = agentClient.plan(planBody);
            detectedSchema = planResult.get("detectedSchema");
            executionPlan = planResult.get("executionPlan");

            // If schema is still ambiguous (codeField empty), use Agent's recommended field from confirmPayload
            if (detectedSchema instanceof Map) {
                Map<String, Object> schemaMap = (Map<String, Object>) detectedSchema;
                Object codeField = schemaMap.get("codeField");
                if (codeField == null || "".equals(codeField)) {
                    Object confirmPayload = planResult.get("confirmPayload");
                    if (confirmPayload instanceof Map) {
                        Map<String, Object> cp = (Map<String, Object>) confirmPayload;
                        Map<String, Object> resolvedSchema = new HashMap<>(schemaMap);
                        resolvedSchema.put("codeField", cp.getOrDefault("recommendedCodeField", ""));
                        resolvedSchema.put("docstringField", cp.getOrDefault("recommendedDocstringField", schemaMap.get("docstringField")));
                        resolvedSchema.put("languageField", cp.getOrDefault("recommendedLanguageField", schemaMap.get("languageField")));
                        detectedSchema = resolvedSchema;
                    }
                }
            }
        }

        // Sync executionPlan with final mergedOptions (add or remove optional skills)
        if (executionPlan instanceof List) {
            List<String> plan = new ArrayList<>((List<String>) executionPlan);
            boolean wantInstructionPairs = Boolean.TRUE.equals(mergedOptions.get("enableInstructionPairs"));
            boolean wantAugmentation = Boolean.TRUE.equals(mergedOptions.get("enableAugmentation"));
            if (wantInstructionPairs && !plan.contains("build_instruction_pairs")) {
                int insertAt = plan.indexOf("deduplicate_samples");
                plan.add(insertAt >= 0 ? insertAt + 1 : plan.size(), "build_instruction_pairs");
            } else if (!wantInstructionPairs) {
                plan.remove("build_instruction_pairs");
            }
            if (wantAugmentation && !plan.contains("rename_variables_augmentation")) {
                int insertAt = plan.indexOf("deduplicate_samples");
                plan.add(insertAt >= 0 ? insertAt + 1 : plan.size(), "rename_variables_augmentation");
            } else if (!wantAugmentation) {
                plan.remove("rename_variables_augmentation");
            }
            executionPlan = plan;
        }

        return doExecute(derived, rawFile.getFilePath(), rawFile.getFileType(),
                detectedSchema, executionPlan, mergedOptions);
    }

    @SuppressWarnings("unchecked")
    public MetricsDiffResponse compareRounds(Long taskId, Long otherTaskId) {
        AnalysisReport r1 = reportRepo.selectOne(
                new LambdaQueryWrapper<AnalysisReport>()
                        .eq(AnalysisReport::getTaskId, taskId).last("LIMIT 1"));
        AnalysisReport r2 = reportRepo.selectOne(
                new LambdaQueryWrapper<AnalysisReport>()
                        .eq(AnalysisReport::getTaskId, otherTaskId).last("LIMIT 1"));

        Object m1 = r1 != null && r1.getReportJson() instanceof Map
                ? ((Map<String, Object>) r1.getReportJson()).get("metrics") : null;
        Object m2 = r2 != null && r2.getReportJson() instanceof Map
                ? ((Map<String, Object>) r2.getReportJson()).get("metrics") : null;

        Map<String, Object> diff = new HashMap<>();
        if (m1 instanceof Map && m2 instanceof Map) {
            Map<String, Object> map1 = (Map<String, Object>) m1;
            Map<String, Object> map2 = (Map<String, Object>) m2;
            for (String key : map1.keySet()) {
                Object v1 = map1.get(key);
                Object v2 = map2.get(key);
                if (v1 instanceof Number && v2 instanceof Number) {
                    double d1 = ((Number) v1).doubleValue();
                    double d2 = ((Number) v2).doubleValue();
                    double delta = d2 - d1;
                    double pct = d1 != 0 ? Math.round(delta / d1 * 10000.0) / 100.0 : 0;
                    Map<String, Object> entry = new HashMap<>();
                    entry.put("before", v1);
                    entry.put("after", v2);
                    entry.put("delta", Math.round(delta * 10000.0) / 10000.0);
                    entry.put("deltaPercent", pct);
                    diff.put(key, entry);
                }
            }
        }

        MetricsDiffResponse resp = new MetricsDiffResponse();
        resp.setTaskId(taskId);
        resp.setOtherTaskId(otherTaskId);
        resp.setMetrics(m1);
        resp.setOtherMetrics(m2);
        resp.setDiff(diff);
        return resp;
    }
}
