package com.dataprocess.agent.dto;

import lombok.Data;
import java.util.Map;

@Data
public class MetricsDiffResponse {
    private Long taskId;
    private Long otherTaskId;
    private Object metrics;
    private Object otherMetrics;
    private Map<String, Object> diff;
}
