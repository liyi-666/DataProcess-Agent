package com.dataprocess.agent.repository;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.dataprocess.agent.entity.DatasetTask;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface DatasetTaskRepository extends BaseMapper<DatasetTask> {
}
