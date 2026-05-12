package com.dataprocess.agent.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArrayList;

@Service
@Slf4j
@RequiredArgsConstructor
public class TaskProgressService {

    private static final long SSE_TIMEOUT_MS = 30 * 60 * 1000L;

    private final ObjectMapper objectMapper;

    private final ConcurrentHashMap<Long, CopyOnWriteArrayList<SseEmitter>> emitters = new ConcurrentHashMap<>();
    private final ConcurrentHashMap<Long, String> lastEvent = new ConcurrentHashMap<>();

    public SseEmitter subscribe(Long taskId) {
        SseEmitter emitter = new SseEmitter(SSE_TIMEOUT_MS);
        emitters.computeIfAbsent(taskId, k -> new CopyOnWriteArrayList<>()).add(emitter);

        Runnable cleanup = () -> {
            CopyOnWriteArrayList<SseEmitter> list = emitters.get(taskId);
            if (list != null) list.remove(emitter);
        };
        emitter.onCompletion(cleanup);
        emitter.onTimeout(cleanup);
        emitter.onError(e -> cleanup.run());

        // 回放最近一次事件，让晚加入的订阅者立即获得当前进度
        String cached = lastEvent.get(taskId);
        if (cached != null) {
            try {
                emitter.send(SseEmitter.event().data(cached));
            } catch (Exception e) {
                cleanup.run();
            }
        }
        return emitter;
    }

    public void publish(Long taskId, Map<String, Object> payload) {
        try {
            String json = objectMapper.writeValueAsString(payload);
            lastEvent.put(taskId, json);
            CopyOnWriteArrayList<SseEmitter> list = emitters.get(taskId);
            if (list == null || list.isEmpty()) return;
            for (SseEmitter emitter : list) {
                try {
                    emitter.send(SseEmitter.event().data(json));
                } catch (Exception e) {
                    list.remove(emitter);
                }
            }
        } catch (Exception e) {
            log.warn("[TaskProgressService] publish failed for taskId={}: {}", taskId, e.getMessage());
        }
    }

    public void complete(Long taskId) {
        CopyOnWriteArrayList<SseEmitter> list = emitters.remove(taskId);
        lastEvent.remove(taskId);
        if (list == null) return;
        for (SseEmitter emitter : list) {
            try { emitter.complete(); } catch (Exception ignored) {}
        }
    }

    public void publishError(Long taskId, String message) {
        Map<String, Object> payload = Map.of(
                "taskId", taskId,
                "event", "task_error",
                "skillName", "",
                "progress", 0,
                "inputCount", 0,
                "outputCount", 0,
                "durationMs", 0,
                "message", message != null ? message : "未知错误"
        );
        publish(taskId, payload);
        complete(taskId);
    }
}
