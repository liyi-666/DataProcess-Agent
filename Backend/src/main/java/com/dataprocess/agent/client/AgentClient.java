package com.dataprocess.agent.client;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.Map;

@Component
public class AgentClient {

    @Value("${agent.base-url:http://localhost:8000}")
    private String baseUrl;

    private final HttpClient httpClient = HttpClient.newBuilder()
            .version(HttpClient.Version.HTTP_1_1)
            .connectTimeout(Duration.ofSeconds(10))
            .build();
    private final ObjectMapper objectMapper = new ObjectMapper();

    public Map<String, Object> plan(Map<String, Object> body) {
        return post("/agent/plan", body);
    }

    public Map<String, Object> execute(Map<String, Object> body) {
        return post("/agent/execute", body);
    }

    public Map<String, Object> chat(Map<String, Object> body) {
        return post("/agent/chat", body);
    }

    public Map<String, Object> parseIntent(Map<String, Object> body) {
        return post("/agent/parse-intent", body);
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> post(String path, Map<String, Object> body) {
        try {
            String json = objectMapper.writeValueAsString(body);
            System.out.println("[AgentClient] POST " + path + " body: " + json);
            HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(baseUrl + path))
                    .header("Content-Type", "application/json; charset=UTF-8")
                    .timeout(Duration.ofMinutes(15))
                    .POST(HttpRequest.BodyPublishers.ofString(json, StandardCharsets.UTF_8))
                    .build();
            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() >= 400) {
                throw new RuntimeException("PythonAgent 返回错误 " + response.statusCode() + ": " + response.body());
            }
            return objectMapper.readValue(response.body(), Map.class);
        } catch (RuntimeException e) {
            throw e;
        } catch (Exception e) {
            throw new RuntimeException("调用 PythonAgent 失败: " + path + " - " + e.getMessage(), e);
        }
    }
}
