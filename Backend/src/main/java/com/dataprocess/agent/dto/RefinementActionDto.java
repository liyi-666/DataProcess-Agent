package com.dataprocess.agent.dto;

import lombok.Data;
import java.util.List;
import java.util.Map;

@Data
public class RefinementActionDto {
    // rerun_with_options | clarify | compare
    private String actionType;
    private String intentSummary;
    // maximize_retention | maximize_quality | balance_retain_and_quality |
    // training_data_construction | reduce_noise | data_augmentation | compare_rounds
    private String optimizationGoal;
    private List<String> strategyReason;
    // 仅包含需要变更的选项字段
    private Map<String, Object> optionsDiff;
    // 过滤阈值放宽，如 {"docstringMinLen": 3}
    private Map<String, Object> filterRelax;
    private List<String> expectedImpact;
    private List<String> riskWarnings;
    // high | medium | low
    private String confidence;
    private String clarificationNeeded;
}
