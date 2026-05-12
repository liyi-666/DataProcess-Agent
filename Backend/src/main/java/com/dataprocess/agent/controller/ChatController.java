package com.dataprocess.agent.controller;

import com.dataprocess.agent.common.Result;
import com.dataprocess.agent.dto.ChatSendRequest;
import com.dataprocess.agent.service.ChatService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/chat")
@RequiredArgsConstructor
public class ChatController {

    private final ChatService chatService;

    @PostMapping("/send")
    public Result<Object> send(@RequestBody ChatSendRequest req) {
        return Result.success(chatService.send(req.getTaskId(), req.getMessage()));
    }
}
