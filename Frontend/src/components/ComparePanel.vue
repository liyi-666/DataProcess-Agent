<template>
  <el-card class="compare-card">
    <template #header>
      <div class="compare-header">
        <span class="compare-title">轮次对比</span>
        <span class="compare-subtitle">任务 #{{ otherTaskId }} → #{{ taskId }}</span>
      </div>
    </template>

    <div v-if="loading" class="compare-loading">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>加载对比数据...</span>
    </div>

    <div v-else-if="error" class="compare-error">{{ error }}</div>

    <div v-else-if="rows.length" class="compare-table-wrap">
      <div class="compare-row compare-row--head">
        <div class="compare-cell compare-cell--label">指标</div>
        <div class="compare-cell compare-cell--num">本轮</div>
        <div class="compare-cell compare-cell--num">上一轮</div>
        <div class="compare-cell compare-cell--delta">变化</div>
      </div>
      <div
        v-for="(row, i) in rows"
        :key="row.label"
        class="compare-row"
        :class="{ 'compare-row--alt': i % 2 === 1 }"
      >
        <div class="compare-cell compare-cell--label">{{ row.label }}</div>
        <div class="compare-cell compare-cell--num compare-cell--bold">{{ row.afterFmt ?? '-' }}</div>
        <div class="compare-cell compare-cell--num compare-cell--muted">{{ row.beforeFmt ?? '-' }}</div>
        <div class="compare-cell compare-cell--delta">
          <span class="delta-badge" :class="deltaBadgeClass(row.delta)">
            {{ row.delta > 0 ? '+' : '' }}{{ row.delta }}
          </span>
          <span v-if="row.deltaPercent !== undefined" class="delta-pct">
            ({{ row.deltaPercent > 0 ? '+' : '' }}{{ row.deltaPercent }}%)
          </span>
        </div>
      </div>
    </div>

    <div v-else class="compare-empty">暂无可对比数据</div>
  </el-card>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  taskId: { type: Number, required: true },
  otherTaskId: { type: Number, required: true },
  currentMetrics: { type: Object, default: () => ({}) },
  previousMetrics: { type: Object, default: () => ({}) },
})

const METRIC_LABELS = {
  rawSampleCount:          '原始样本数',
  finalSampleCount:        '最终样本数',
  retainRate:              '保留率',
  astParseSuccessCount:    'AST 解析成功',
  astParseFailedCount:     'AST 解析失败',
  emptyCodeCount:          '空代码数',
  lowQualityDocstringCount:'低质量文档数',
  dedupRemovedCount:       '去重删除数',
  augmentationSuccessCount:'增强成功数',
  syntaxPassRate:          '语法通过率',
  docstringCoverage:       'Docstring 覆盖率',
}

const RATE_KEYS = new Set(['retainRate', 'syntaxPassRate', 'docstringCoverage'])

function fmt(key, val) {
  if (val == null) return '-'
  if (RATE_KEYS.has(key)) return (val * 100).toFixed(1) + '%'
  return val
}

const rows = computed(() => {
  const cur = props.currentMetrics || {}
  const prev = props.previousMetrics || {}
  const keys = Object.keys(METRIC_LABELS)
  return keys
    .filter(k => cur[k] != null || prev[k] != null)
    .map(k => {
      const after = cur[k] ?? null
      const before = prev[k] ?? null
      let delta = null
      let deltaPercent = null
      if (after != null && before != null) {
        delta = RATE_KEYS.has(k)
          ? parseFloat(((after - before) * 100).toFixed(2))
          : parseFloat((after - before).toFixed(2))
        deltaPercent = before !== 0
          ? parseFloat(((after - before) / Math.abs(before) * 100).toFixed(1))
          : null
      }
      return {
        label: METRIC_LABELS[k],
        afterRaw: after,
        beforeRaw: before,
        afterFmt: fmt(k, after),
        beforeFmt: fmt(k, before),
        delta,
        deltaPercent,
      }
    })
})

function deltaBadgeClass(delta) {
  if (delta > 0) return 'delta-badge--up'
  if (delta < 0) return 'delta-badge--down'
  return 'delta-badge--flat'
}
</script>

<style scoped>
.compare-header {
  display: flex;
  align-items: center;
  gap: 10px;
}

.compare-title {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
}

.compare-subtitle {
  font-size: 12px;
  color: #909399;
  background: #f5f7fa;
  padding: 2px 8px;
  border-radius: 4px;
}

.compare-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 24px;
  font-size: 13px;
  color: #909399;
}

.compare-error {
  font-size: 13px;
  color: #f56c6c;
  padding: 8px 0;
}

.compare-empty {
  font-size: 13px;
  color: #909399;
  text-align: center;
  padding: 24px;
}

.compare-table-wrap {
  border: 1px solid #e8eaed;
  border-radius: 6px;
  overflow: hidden;
}

.compare-row {
  display: grid;
  grid-template-columns: 1fr 100px 100px 120px;
  align-items: center;
  border-bottom: 1px solid #f0f2f5;
}

.compare-row:last-child {
  border-bottom: none;
}

.compare-row--head {
  background: #f5f7fa;
}

.compare-row--alt {
  background: #fafafa;
}

.compare-cell {
  padding: 10px 12px;
  font-size: 13px;
}

.compare-cell--label {
  color: #303133;
  font-weight: 500;
}

.compare-row--head .compare-cell {
  font-size: 12px;
  font-weight: 600;
  color: #606266;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

.compare-cell--num {
  text-align: right;
}

.compare-cell--muted {
  color: #909399;
}

.compare-cell--bold {
  color: #303133;
  font-weight: 600;
}

.compare-cell--delta {
  text-align: right;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 4px;
}

.delta-badge {
  font-size: 12px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 4px;
}

.delta-badge--up {
  color: #67c23a;
  background: #f0f9eb;
}

.delta-badge--down {
  color: #f56c6c;
  background: #fef0f0;
}

.delta-badge--flat {
  color: #909399;
  background: #f5f7fa;
}

.delta-pct {
  font-size: 11px;
  color: #909399;
}
</style>
