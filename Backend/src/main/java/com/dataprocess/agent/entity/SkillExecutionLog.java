package com.dataprocess.agent.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

@Data
@TableName("skill_execution_log")
public class SkillExecutionLog {

    @TableId(type = IdType.AUTO)
    private Long id;

    private Long taskId;

    private String skillName;

    private Integer executionOrder;

    private String executionStatus;

    private String inputSummary;

    private String outputSummary;

    private Long executionTimeMs;

    private String errorMessage;
}
