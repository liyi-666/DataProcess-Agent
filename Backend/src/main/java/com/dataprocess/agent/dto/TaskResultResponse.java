package com.dataprocess.agent.dto;

import lombok.Data;
import java.util.List;

@Data
public class TaskResultResponse {
    private Long taskId;
    private String taskStatus;
    private String summary;
    private Object metrics;
    private List<Object> charts;
    private List<Object> outputFiles;
    private List<Object> executionLogs;
    private String reflectionSummary;
    private List<String> qualityWarnings;
    private List<String> nextStepSuggestions;
    private Object options;
}
