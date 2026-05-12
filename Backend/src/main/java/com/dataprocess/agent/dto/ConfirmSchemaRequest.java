package com.dataprocess.agent.dto;

import lombok.Data;

@Data
public class ConfirmSchemaRequest {
    private String codeField;
    private String docstringField;
    private String languageField;
}
