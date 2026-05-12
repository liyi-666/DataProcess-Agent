package com.dataprocess.agent.dto;

import lombok.Data;

@Data
public class ChatSendRequest {
    private Long taskId;
    private String message;
}
