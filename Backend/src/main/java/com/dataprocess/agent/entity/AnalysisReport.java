package com.dataprocess.agent.entity;

import com.baomidou.mybatisplus.annotation.*;
import com.baomidou.mybatisplus.extension.handlers.JacksonTypeHandler;
import com.fasterxml.jackson.annotation.JsonFormat;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@TableName(value = "analysis_report", autoResultMap = true)
public class AnalysisReport {

    @TableId(type = IdType.AUTO)
    private Long id;

    private Long taskId;

    @TableField(typeHandler = JacksonTypeHandler.class)
    private Object reportJson;

    private String summaryText;

    @TableField(fill = FieldFill.INSERT)
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime createTime;
}
