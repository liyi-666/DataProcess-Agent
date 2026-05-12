package com.dataprocess.agent.repository;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.dataprocess.agent.entity.ChatMessage;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface ChatMessageRepository extends BaseMapper<ChatMessage> {
}
