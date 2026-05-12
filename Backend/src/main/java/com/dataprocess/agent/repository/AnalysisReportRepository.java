package com.dataprocess.agent.repository;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.dataprocess.agent.entity.AnalysisReport;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface AnalysisReportRepository extends BaseMapper<AnalysisReport> {
}
