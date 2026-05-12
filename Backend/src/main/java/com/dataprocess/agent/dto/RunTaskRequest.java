package com.dataprocess.agent.dto;

import lombok.Data;

@Data
public class RunTaskRequest {
    private Boolean useDefaultPlan = true;
    private ProcessingOptions options = new ProcessingOptions();

    @Data
    public static class ProcessingOptions {
        private Boolean enableDedup = true;
        private Boolean enableAstDedup = true;
        private Boolean enableAstExtract = true;
        private Boolean enableAugmentation = false;
        private Boolean enableInstructionPairs = true;
        private String sampleUnitType = "function";
        private String sourceGranularity = "function";
    }
}
