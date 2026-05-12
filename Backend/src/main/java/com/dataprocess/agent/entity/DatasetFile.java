package com.dataprocess.agent.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

@Data
@TableName("dataset_file")
public class DatasetFile {

    @TableId(type = IdType.AUTO)
    private Long id;

    private Long taskId;

    private String fileName;

    private String fileType;

    private String fileRole;

    private String storageType;

    private String filePath;

    private String fileUrl;

    private Long fileSize;
}
