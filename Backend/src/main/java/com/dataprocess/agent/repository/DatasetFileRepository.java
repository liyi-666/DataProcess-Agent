package com.dataprocess.agent.repository;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.dataprocess.agent.entity.DatasetFile;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface DatasetFileRepository extends BaseMapper<DatasetFile> {
}
