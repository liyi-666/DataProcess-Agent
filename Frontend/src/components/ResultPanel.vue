<template>
  <div class="result-panel">
    <!-- 详细指标卡网格 -->
    <el-card v-if="showMetrics && result.metrics && hasSecondaryMetrics" class="metrics-detail-card">
      <template #header>详细指标</template>
      <div class="metrics-detail-grid">
        <div v-if="result.metrics.docstringCoverage != null" class="mdi-card">
          <div class="mdi-value" :class="rateClass(result.metrics.docstringCoverage)">
            {{ pct(result.metrics.docstringCoverage) }}
          </div>
          <div class="mdi-label">文档覆盖率</div>
        </div>

        <template v-if="hasDedup">
          <div v-if="result.metrics.exactDedupRemovedCount != null" class="mdi-card">
            <div class="mdi-value mdi-value--warn">{{ result.metrics.exactDedupRemovedCount }}</div>
            <div class="mdi-label">精确去重删除</div>
          </div>
          <div v-if="result.metrics.astDedupRemovedCount != null" class="mdi-card">
            <div class="mdi-value mdi-value--warn">{{ result.metrics.astDedupRemovedCount }}</div>
            <div class="mdi-label">AST 去重删除</div>
          </div>
        </template>
        <div v-else-if="result.metrics.dedupRemovedCount != null" class="mdi-card">
          <div class="mdi-value mdi-value--warn">{{ result.metrics.dedupRemovedCount }}</div>
          <div class="mdi-label">去重删除数</div>
        </div>

        <div v-if="result.metrics.astParseSuccessCount != null" class="mdi-card">
          <div class="mdi-value mdi-value--good">{{ result.metrics.astParseSuccessCount }}</div>
          <div class="mdi-label">AST 解析成功</div>
        </div>
        <div v-if="result.metrics.astParseFailedCount != null" class="mdi-card">
          <div class="mdi-value mdi-value--warn">{{ result.metrics.astParseFailedCount }}</div>
          <div class="mdi-label">AST 解析失败</div>
        </div>
        <div v-if="result.metrics.augmentationSuccessCount != null" class="mdi-card">
          <div class="mdi-value">{{ result.metrics.augmentationSuccessCount }}</div>
          <div class="mdi-label">增强成功数</div>
        </div>
        <div v-if="result.metrics.functionNameMatchRate != null" class="mdi-card">
          <div class="mdi-value" :class="rateClass(result.metrics.functionNameMatchRate)">
            {{ pct(result.metrics.functionNameMatchRate) }}
          </div>
          <div class="mdi-label">函数名匹配率</div>
        </div>
        <div v-if="enableInstructionPairs && result.metrics.instructionPairCount != null" class="mdi-card">
          <div class="mdi-value" :class="result.metrics.instructionPairCount > 0 ? 'mdi-value--good' : 'mdi-value--warn'">
            {{ result.metrics.instructionPairCount }}
          </div>
          <div class="mdi-label">指令对数量</div>
        </div>
      </div>
    </el-card>

    <!-- 处理成果 -->
    <el-card v-if="showFiles && result.outputFiles && result.outputFiles.length" class="output-card">
      <template #header>处理成果</template>

      <div v-if="primaryFiles.length" class="file-section">
        <div class="file-section-label">主结果</div>
        <div v-for="f in primaryFiles" :key="f.fileId" class="file-card file-card--primary">
          <div class="file-card-body">
            <div class="file-card-top">
              <el-tag type="primary" size="small">{{ roleLabel(f.fileRole) }}</el-tag>
              <span class="file-name">{{ f.fileName }}</span>
            </div>
            <div class="file-desc">{{ roleDesc(f.fileRole) }}</div>
            <div v-if="roleNextStep(f.fileRole)" class="file-next">{{ roleNextStep(f.fileRole) }}</div>
          </div>
          <el-button size="small" type="primary" plain class="file-dl-btn" @click="downloadFile(f.fileId)">下载</el-button>
        </div>

        <div v-if="enableInstructionPairs && !hasInstructionPairsFile" class="no-pairs-hint">
          <span class="no-pairs-icon">!</span>
          <span>指令对文件未生成：数据集中未找到可解析的 Python 函数定义，或 AST 解析全部失败。请确认代码字段包含完整的 Python 函数，或检查 AST 解析失败数量。</span>
        </div>
      </div>

      <div v-if="secondaryFiles.length" class="file-section">
        <div class="file-section-label">辅助文件</div>
        <div v-for="f in secondaryFiles" :key="f.fileId" class="file-card file-card--secondary">
          <div class="file-card-body">
            <div class="file-card-top">
              <el-tag :type="roleTagType(f.fileRole)" size="small">{{ roleLabel(f.fileRole) }}</el-tag>
              <span class="file-name">{{ f.fileName }}</span>
            </div>
            <div class="file-desc">{{ roleDesc(f.fileRole) }}</div>
          </div>
          <el-button size="small" plain class="file-dl-btn" @click="downloadFile(f.fileId)">下载</el-button>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { downloadFile } from '../api/task'

const props = defineProps({
  result: { type: Object, required: true },
  section: { type: String, default: 'all' }, // 'all' | 'metrics' | 'files'
})

const showMetrics = computed(() => props.section === 'all' || props.section === 'metrics')
const showFiles = computed(() => props.section === 'all' || props.section === 'files')

const enableInstructionPairs = computed(() => {
  const opts = props.result.options
  if (!opts) return true
  return opts.enableInstructionPairs !== false
})

const hasInstructionPairsFile = computed(() =>
  (props.result.outputFiles || []).some(f => f.fileRole === 'instruction_pairs')
)

const PRIMARY_ROLES = ['cleaned', 'instruction_pairs']

const primaryFiles = computed(() =>
  (props.result.outputFiles || []).filter(f => {
    if (f.fileRole === 'instruction_pairs' && !enableInstructionPairs.value) return false
    return PRIMARY_ROLES.includes(f.fileRole)
  })
)
const secondaryFiles = computed(() =>
  (props.result.outputFiles || []).filter(f => {
    if (f.fileRole === 'instruction_pairs' && !enableInstructionPairs.value) return false
    return !PRIMARY_ROLES.includes(f.fileRole)
  })
)

const hasDedup = computed(() => {
  const m = props.result.metrics
  return m && (m.exactDedupRemovedCount != null || m.astDedupRemovedCount != null)
})

const hasSecondaryMetrics = computed(() => {
  const m = props.result.metrics
  return m && (
    m.docstringCoverage != null || m.dedupRemovedCount != null ||
    m.exactDedupRemovedCount != null || m.astDedupRemovedCount != null ||
    m.astParseSuccessCount != null || m.astParseFailedCount != null ||
    m.augmentationSuccessCount != null || m.functionNameMatchRate != null ||
    (enableInstructionPairs.value && m.instructionPairCount != null)
  )
})

function pct(val) {
  if (val == null) return '-'
  return (val * 100).toFixed(1) + '%'
}

function rateClass(val) {
  if (val == null) return ''
  if (val >= 0.8) return 'mdi-value--good'
  if (val >= 0.5) return 'mdi-value--warn'
  return 'mdi-value--danger'
}

const ROLE_META = {
  cleaned:           { label: '主结果',    tagType: 'primary', desc: '预处理后的主结果数据集',              next: '可直接用于模型训练或进一步分析' },
  instruction_pairs: { label: '指令样本对', tagType: 'primary', desc: '构造出的 docstring→code 训练样本对',  next: '可用于代码生成任务的指令微调训练' },
  preview:           { label: '预览',      tagType: 'info',    desc: '结果数据集的部分样本预览',             next: '可快速抽查处理效果，无需下载完整文件' },
  stats:             { label: '统计',      tagType: 'success', desc: '数据集统计指标（样本数、覆盖率等）',    next: '可用于质量评估和处理报告' },
  badcase:           { label: '坏样本',    tagType: 'warning', desc: '被过滤或 AST 解析失败的样本',         next: '可人工抽查，分析过滤原因' },
  report:            { label: '报告',      tagType: 'info',    desc: '完整的处理分析报告',                  next: '可归档或分享给团队' },
}

function roleMeta(role) {
  return ROLE_META[role] || { label: role || '未知', tagType: '', desc: '处理输出文件', next: '' }
}

function roleLabel(role)    { return roleMeta(role).label }
function roleTagType(role)  { return roleMeta(role).tagType }
function roleDesc(role)     { return roleMeta(role).desc }
function roleNextStep(role) { return roleMeta(role).next ? '→ ' + roleMeta(role).next : '' }
</script>

<style scoped>
.result-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* 详细指标卡网格 */
.metrics-detail-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}

.mdi-card {
  background: #fafafa;
  border: 1px solid #f0f2f5;
  border-radius: 6px;
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.mdi-value {
  font-size: 22px;
  font-weight: 700;
  color: #303133;
  line-height: 1.2;
}

.mdi-value--good    { color: #67c23a; }
.mdi-value--warn    { color: #e6a23c; }
.mdi-value--danger  { color: #f56c6c; }

.mdi-label {
  font-size: 12px;
  color: #909399;
}

/* 文件卡片 */
.file-section {
  margin-bottom: 16px;
}

.file-section:last-child { margin-bottom: 0; }

.file-section-label {
  font-size: 11px;
  color: #909399;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 8px;
}

.file-card {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding: 12px 14px;
  border-radius: 6px;
  margin-bottom: 8px;
}

.file-card:last-child { margin-bottom: 0; }

.file-card--primary {
  border: 1px solid rgba(64,158,255,0.25);
  border-left: 3px solid #409eff;
  background: #f0f7ff;
}

.file-card--secondary {
  border: 1px solid #e4e7ed;
  background: #fafafa;
}

.file-card-body {
  flex: 1;
  min-width: 0;
}

.file-card-top {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.file-name {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
  word-break: break-all;
}

.file-desc {
  font-size: 12px;
  color: #606266;
  margin-bottom: 2px;
}

.file-next {
  font-size: 12px;
  color: #909399;
}

.file-dl-btn {
  margin-left: 12px;
  flex-shrink: 0;
}

.no-pairs-hint {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-top: 8px;
  padding: 10px 12px;
  background: #fdf6ec;
  border: 1px solid #f5dab1;
  border-radius: 6px;
  font-size: 12px;
  color: #7a5c00;
  line-height: 1.5;
}

.no-pairs-icon {
  width: 16px;
  height: 16px;
  background: #e6a23c;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  color: #fff;
  flex-shrink: 0;
  margin-top: 1px;
}
</style>
