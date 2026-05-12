<template>
  <el-card class="timeline-card">
    <template #header>
      <div class="timeline-header">
        <span class="timeline-title">执行日志</span>
        <span v-if="isRunning" class="running-badge">
          <span class="running-dot"></span>运行中
        </span>
        <span v-else-if="logs.length" class="log-count">{{ logs.length }} 个步骤</span>
        <button v-if="logs.length > COLLAPSE_THRESHOLD" class="expand-btn" @click="expanded = !expanded">
          {{ expanded ? '收起' : '展开全部' }}
        </button>
      </div>
    </template>

    <div v-if="!logs.length && !isRunning" class="empty-state">暂无执行日志</div>

    <div class="timeline">
      <div
        v-for="(log, i) in visibleLogs"
        :key="i"
        class="timeline-item"
        :class="'item-' + log.status"
      >
        <!-- 连接线 + 图标 -->
        <div class="item-track">
          <div class="item-icon" :class="'icon-' + log.status">
            <span v-if="log.status === 'success'">✓</span>
            <span v-else-if="log.status === 'error' || log.status === 'failed'">✗</span>
            <span v-else-if="log.status === 'skipped'">–</span>
            <span v-else>·</span>
          </div>
          <div v-if="i < visibleLogs.length - 1 || isRunning" class="item-line"></div>
        </div>

        <!-- 内容 -->
        <div class="item-body">
          <div class="item-top">
            <span class="item-skill">{{ skillLabel(log.skillName) }}</span>
            <span class="item-duration" v-if="log.durationMs">{{ formatDuration(log.durationMs) }}</span>
          </div>

          <div class="item-counts" v-if="log.inputCount || log.outputCount">
            <span class="count-in">{{ log.inputCount }} 条输入</span>
            <span class="count-arrow">→</span>
            <span class="count-out" :class="{ 'count-reduced': log.removedCount > 0 }">
              {{ log.outputCount }} 条输出
            </span>
            <span v-if="log.removedCount > 0" class="count-removed">
              （过滤 {{ log.removedCount }} 条）
            </span>
          </div>

          <div v-if="log.message" class="item-message" :class="'msg-' + log.status">
            {{ log.message }}
          </div>
        </div>
      </div>

      <!-- 运行中占位 -->
      <div v-if="isRunning" class="timeline-item item-running">
        <div class="item-track">
          <div class="item-icon icon-running">
            <span class="spinner"></span>
          </div>
        </div>
        <div class="item-body">
          <div class="item-top">
            <span class="item-skill">{{ currentSkill ? skillLabel(currentSkill) : '处理中...' }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 折叠提示 -->
    <div v-if="!expanded && logs.length > COLLAPSE_THRESHOLD" class="collapse-hint">
      还有 {{ logs.length - COLLAPSE_THRESHOLD }} 个步骤已折叠
      <button class="expand-btn-inline" @click="expanded = true">展开</button>
    </div>
  </el-card>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  logs: { type: Array, default: () => [] },
  isRunning: { type: Boolean, default: false },
  currentSkill: { type: String, default: '' },
})

const COLLAPSE_THRESHOLD = 4
const expanded = ref(false)

const visibleLogs = computed(() => {
  if (expanded.value || props.logs.length <= COLLAPSE_THRESHOLD) return props.logs
  return props.logs.slice(0, COLLAPSE_THRESHOLD)
})

const SKILL_LABELS = {
  load_dataset: '加载数据集',
  normalize_code_text: '代码文本规范化',
  extract_function_structure: 'AST 函数结构提取',
  filter_invalid_samples: '过滤无效样本',
  filter_low_quality_docstring: '过滤低质量文档',
  deduplicate_samples: '样本去重',
  rename_variables_augmentation: '变量重命名增强',
  build_instruction_pairs: '构造指令样本对',
  compute_dataset_profile: '计算数据画像',
  evaluate_data_quality: '质量评估',
  generate_chart_specs: '生成图表配置',
  detect_dataset_schema: 'Schema 检测',
}

function skillLabel(name) {
  return SKILL_LABELS[name] || name || '未知步骤'
}

function formatDuration(ms) {
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}
</script>

<style scoped>

.timeline-header {
  display: flex;
  align-items: center;
  gap: 10px;
}

.timeline-title {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
  flex: 1;
}

.running-badge {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  color: #409eff;
}

.running-dot {
  width: 7px;
  height: 7px;
  background: #409eff;
  border-radius: 50%;
  animation: pulse 1.4s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

.log-count {
  font-size: 12px;
  color: #909399;
}

.expand-btn {
  background: none;
  border: none;
  color: #409eff;
  font-size: 12px;
  cursor: pointer;
  padding: 0;
}

.expand-btn:hover {
  text-decoration: underline;
}

.empty-state {
  text-align: center;
  color: #c0c4cc;
  font-size: 13px;
  padding: 20px 0;
}

.timeline {
  display: flex;
  flex-direction: column;
}

.timeline-item {
  display: flex;
  gap: 12px;
  min-height: 40px;
}

.item-track {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex-shrink: 0;
  width: 24px;
}

.item-icon {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;
}

.icon-success { background: #f0f9eb; color: #67c23a; border: 1.5px solid #b3e19d; }
.icon-error, .icon-failed { background: #fef0f0; color: #f56c6c; border: 1.5px solid #fbc4c4; }
.icon-skipped { background: #f4f4f5; color: #909399; border: 1.5px solid #dcdfe6; }
.icon-running { background: #ecf5ff; color: #409eff; border: 1.5px solid #b3d8ff; }

.item-line {
  width: 1.5px;
  flex: 1;
  background: #e8eaed;
  margin: 3px 0;
  min-height: 12px;
}

.item-body {
  flex: 1;
  padding-bottom: 14px;
  min-width: 0;
}

.item-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 4px;
  padding-top: 2px;
}

.item-skill {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
}

.item-duration {
  font-size: 11px;
  color: #909399;
  flex-shrink: 0;
}

.item-counts {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  color: #606266;
  margin-bottom: 3px;
}

.count-in { color: #909399; }
.count-arrow { color: #c0c4cc; }
.count-out { color: #303133; font-weight: 500; }
.count-reduced { color: #67c23a; }
.count-removed { color: #e6a23c; }

.item-message {
  font-size: 12px;
  line-height: 1.5;
  color: #606266;
  word-break: break-word;
}

.msg-error, .msg-failed { color: #f56c6c; }
.msg-skipped { color: #909399; font-style: italic; }

.spinner {
  display: inline-block;
  width: 10px;
  height: 10px;
  border: 2px solid #b3d8ff;
  border-top-color: #409eff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.collapse-hint {
  font-size: 12px;
  color: #909399;
  text-align: center;
  padding-top: 4px;
  border-top: 1px dashed #e8eaed;
  margin-top: 4px;
}

.expand-btn-inline {
  background: none;
  border: none;
  color: #409eff;
  font-size: 12px;
  cursor: pointer;
  padding: 0 4px;
}

.expand-btn-inline:hover {
  text-decoration: underline;
}
</style>
