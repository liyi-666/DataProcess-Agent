package com.dataprocess.agent.controller;

import com.dataprocess.agent.entity.DatasetFile;
import com.dataprocess.agent.service.TaskService;
import lombok.RequiredArgsConstructor;
import org.springframework.core.io.FileSystemResource;
import org.springframework.core.io.Resource;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.io.File;

@RestController
@RequestMapping("/api/files")
@RequiredArgsConstructor
public class FileController {

    private final TaskService taskService;

    @GetMapping("/{fileId}/download")
    public ResponseEntity<Resource> download(@PathVariable Long fileId) {
        DatasetFile df = taskService.getFileById(fileId);
        if (df == null) return ResponseEntity.notFound().build();

        File file = new File(df.getFilePath());
        if (!file.exists()) return ResponseEntity.notFound().build();

        Resource resource = new FileSystemResource(file);
        return ResponseEntity.ok()
                .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=\"" + df.getFileName() + "\"")
                .contentType(MediaType.APPLICATION_OCTET_STREAM)
                .body(resource);
    }
}
