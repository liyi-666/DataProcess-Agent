package com.dataprocess.agent.dto;

import lombok.Data;

@Data
public class TaskStatusResponse {
    private Long taskId;
    private String taskStatus;
    private String currentStep;
    private Integer progress;
    private Boolean needUserConfirm;
    private Object confirmPayload;
    private Object planObservations;
    private String errorMessage;
    private Long parentTaskId;
    private Integer roundIndex;
}
