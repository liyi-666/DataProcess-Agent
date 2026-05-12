package com.dataprocess.agent.controller;

import com.dataprocess.agent.common.Result;
import com.dataprocess.agent.dto.ConfirmSchemaRequest;
import com.dataprocess.agent.dto.RefineRunRequest;
import com.dataprocess.agent.dto.RunTaskRequest;
import com.dataprocess.agent.service.TaskProgressService;
import com.dataprocess.agent.service.TaskService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;
import java.util.Map;

@RestController
@RequestMapping("/api/tasks")
@RequiredArgsConstructor
public class TaskController {

    private final TaskService taskService;
    private final TaskProgressService taskProgressService;

    @PostMapping("/upload")
    public Result<Object> upload(
            @RequestParam("file") MultipartFile file,
            @RequestParam(value = "taskName", required = false) String taskName,
            @RequestParam(value = "taskDescription", required = false) String taskDescription) {
        return Result.success(taskService.upload(file, taskName, taskDescription));
    }

    @PostMapping("/{taskId}/plan")
    public Result<Object> plan(@PathVariable Long taskId) {
        return Result.success(taskService.planTask(taskId));
    }

    @PostMapping("/{taskId}/run")
    public Result<Object> run(@PathVariable Long taskId, @RequestBody(required = false) RunTaskRequest req) {
        if (req == null) req = new RunTaskRequest();
        return Result.success("task started", taskService.runTask(taskId, req));
    }

    @GetMapping("/{taskId}/status")
    public Result<Object> status(@PathVariable Long taskId) {
        return Result.success(taskService.getStatus(taskId));
    }

    @PostMapping("/{taskId}/confirm-schema")
    public Result<Object> confirmSchema(@PathVariable Long taskId, @RequestBody ConfirmSchemaRequest req) {
        return Result.success("schema confirmed", taskService.confirmSchema(taskId, req));
    }

    @GetMapping("/{taskId}/result")
    public Result<Object> result(@PathVariable Long taskId) {
        return Result.success(taskService.getResult(taskId));
    }

    @PostMapping("/{taskId}/refine/parse")
    public Result<Object> refineParse(@PathVariable Long taskId, @RequestBody Map<String, Object> req) {
        return Result.success(taskService.parseIntent(taskId, req));
    }

    @PostMapping("/{taskId}/refine/run")
    public Result<Object> refineRun(@PathVariable Long taskId, @RequestBody RefineRunRequest req) {
        return Result.success(taskService.refineRun(taskId, req));
    }

    @GetMapping("/{taskId}/compare/{otherTaskId}")
    public Result<Object> compare(@PathVariable Long taskId, @PathVariable Long otherTaskId) {
        return Result.success(taskService.compareRounds(taskId, otherTaskId));
    }

    @CrossOrigin
    @GetMapping(value = "/{taskId}/progress", produces = "text/event-stream")
    public SseEmitter subscribeProgress(@PathVariable Long taskId) {
        return taskProgressService.subscribe(taskId);
    }

    @PostMapping("/{taskId}/progress/callback")
    public void progressCallback(@PathVariable Long taskId, @RequestBody Map<String, Object> body) {
        taskProgressService.publish(taskId, body);
    }
}
