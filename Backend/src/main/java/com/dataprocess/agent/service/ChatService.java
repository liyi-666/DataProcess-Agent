package com.dataprocess.agent.service;

import com.dataprocess.agent.client.AgentClient;
import com.dataprocess.agent.entity.AnalysisReport;
import com.dataprocess.agent.entity.ChatMessage;
import com.dataprocess.agent.repository.AnalysisReportRepository;
import com.dataprocess.agent.repository.ChatMessageRepository;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.HashMap;
import java.util.Map;

@Service
@RequiredArgsConstructor
public class ChatService {

    private final ChatMessageRepository chatMessageRepo;
    private final AnalysisReportRepository reportRepo;
    private final AgentClient agentClient;

    @SuppressWarnings("unchecked")
    public Map<String, Object> send(Long taskId, String message) {
        ChatMessage userMsg = new ChatMessage();
        userMsg.setTaskId(taskId);
        userMsg.setRole("user");
        userMsg.setContent(message);
        chatMessageRepo.insert(userMsg);

        AnalysisReport report = reportRepo.selectOne(
                new LambdaQueryWrapper<AnalysisReport>()
                        .eq(AnalysisReport::getTaskId, taskId)
                        .last("LIMIT 1")
        );

        Object metrics = null;
        Object executionLogs = null;
        Object summary = null;
        if (report != null && report.getReportJson() instanceof Map) {
            Map<String, Object> reportMap = (Map<String, Object>) report.getReportJson();
            metrics = reportMap.get("metrics");
            executionLogs = reportMap.get("executionLogs");
            summary = reportMap.get("summary");
        }

        Map<String, Object> chatBody = new HashMap<>();
        chatBody.put("taskId", taskId);
        chatBody.put("message", message);
        chatBody.put("metrics", metrics);
        chatBody.put("executionLogs", executionLogs);
        chatBody.put("summary", summary);

        Map<String, Object> agentResp = agentClient.chat(chatBody);

        String reply = (String) agentResp.getOrDefault("reply", "");
        ChatMessage assistantMsg = new ChatMessage();
        assistantMsg.setTaskId(taskId);
        assistantMsg.setRole("assistant");
        assistantMsg.setContent(reply);
        chatMessageRepo.insert(assistantMsg);

        Map<String, Object> result = new HashMap<>();
        result.put("reply", reply);
        result.put("referMetrics", agentResp.get("referMetrics"));
        return result;
    }
}
