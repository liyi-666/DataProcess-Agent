package com.dataprocess.agent.entity;

import com.baomidou.mybatisplus.annotation.*;
import com.fasterxml.jackson.annotation.JsonFormat;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@TableName(value = "dataset_task", autoResultMap = true)
public class DatasetTask {

    @TableId(type = IdType.AUTO)
    private Long id;

    private String taskName;

    private String taskDescription;

    private String taskStatus;

    private String currentStep;

    private Integer progress;

    private Boolean needUserConfirm;

    @TableField(typeHandler = com.baomidou.mybatisplus.extension.handlers.JacksonTypeHandler.class)
    private Object confirmPayload;

    @TableField(typeHandler = com.baomidou.mybatisplus.extension.handlers.JacksonTypeHandler.class)
    private Object planObservations;

    private String errorMessage;

    private Long parentTaskId;

    private Integer roundIndex;

    private String refinementAction;

    @TableField(fill = FieldFill.INSERT)
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime createTime;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime updateTime;
}
