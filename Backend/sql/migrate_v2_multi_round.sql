-- 多轮协作式二次处理：为 dataset_task 表添加派生任务字段
ALTER TABLE dataset_task
    ADD COLUMN parent_task_id  BIGINT  NULL COMMENT '父任务 ID，NULL 表示首轮任务',
    ADD COLUMN round_index     INT     NOT NULL DEFAULT 0 COMMENT '处理轮次，首轮为 0',
    ADD COLUMN refinement_action TEXT  NULL COMMENT '本轮优化动作 JSON（RefinementAction）';
