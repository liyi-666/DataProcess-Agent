<template>
  <div class="task-page">

    <!-- 页面标题行 -->
    <div class="page-header">
      <el-button class="back-btn" @click="router.push('/')">← 返回</el-button>
      <div class="page-title-group">
        <h2 class="page-title">任务 <span class="task-id-accent">#{{ taskId }}</span></h2>
        <span v-if="status.taskStatus" class="status-tag-wrap">
          <span class="status-dot" :class="'dot-' + (status.taskStatus || '').toLowerCase()"></span>
          <el-tag :type="statusTagType" size="small">{{ statusLabel(status.taskStatus) }}</el-tag>
        </span>
      </div>
    </div>

    <!-- 状态卡片（任务运行中时显示） -->
    <el-card v-if="!result" class="status-card">
      <div class="status-body">
        <div class="status-info">
          <div class="status-step-label">当前步骤</div>
          <div class="status-step-name">{{ stepLabel(status.currentStep) }}</div>
        </div>
        <div class="status-progress-wrap">
          <div class="progress-pct">{{ Math.round(displayProgress) }}%</div>
          <el-progress
            :percentage="displayProgress"
            :status="progressStatus"
            :stroke-width="8"
            :show-text="false"
            class="status-progress"
          />
        </div>
      </div>
      <el-alert
        v-if="status.taskStatus === 'FAILED'"
        class="fail-alert"
        :title="status.errorMessage || '任务执行失败'"
        type="error"
        :closable="false"
      />
      <el-alert
        v-if="showLongRunningHint"
        class="long-running-alert"
        title="处理时间较长，任务仍在运行中，请耐心等待"
        type="info"
        :closable="false"
        show-icon
      />
    </el-card>

    <!-- 任务完成后的进度条（折叠态） -->
    <div v-if="result" class="status-bar-compact">
      <span class="status-bar-step">{{ stepLabel(status.currentStep) }}</span>
      <div class="status-bar-right">
        <span class="status-bar-pct">{{ Math.round(displayProgress) }}%</span>
        <el-progress
          :percentage="displayProgress"
          :status="progressStatus"
          :stroke-width="5"
          :show-text="false"
          class="status-bar-progress"
        />
      </div>
    </div>

    <!-- 字段确认 -->
    <SchemaConfirmDialog
      v-if="status.taskStatus === 'WAITING_CONFIRM' && status.confirmPayload"
      :confirm-payload="status.confirmPayload"
      class="confirm-card"
      @confirm="handleConfirm"
    />

    <!-- 执行中实时日志 -->
    <ExecutionTimeline
      v-if="!result && (isRunning || liveExecutionLogs.length > 0)"
      :logs="liveExecutionLogs"
      :is-running="isRunning"
      :current-skill="currentSkill"
    />

    <!-- 结果区域 -->
    <template v-if="result">
      <!-- 全宽 Hero：成功 Banner + 4 核心指标 -->
      <div class="result-hero">
        <div class="hero-banner">
          <div class="hero-banner-inner">
            <span class="hero-icon">✓</span>
            <div class="hero-text">
              <div class="hero-title">预处理完成</div>
              <div v-if="result.summary" class="hero-sub">{{ result.summary }}</div>
            </div>
          </div>
        </div>

        <div v-if="result.metrics" class="hero-metrics">
          <div class="hero-metric-card">
            <div class="hero-metric-value">{{ fmt(result.metrics.rawSampleCount) }}</div>
            <div class="hero-metric-label">原始样本数</div>
          </div>
          <div class="hero-metric-card hero-metric-card--primary">
            <div class="hero-metric-value hero-metric-value--blue">{{ fmt(result.metrics.finalSampleCount) }}</div>
            <div class="hero-metric-label">最终样本数</div>
          </div>
          <div class="hero-metric-card hero-metric-card--circle">
            <el-progress
              type="circle"
              :percentage="pctNum(result.metrics.retainRate)"
              :color="rateColor(result.metrics.retainRate)"
              :stroke-width="7"
              :width="68"
            >
              <template #default="{ percentage }">
                <span class="circle-pct" :style="{ color: rateColor(result.metrics.retainRate) }">{{ percentage }}%</span>
              </template>
            </el-progress>
            <div class="hero-metric-label">保留率</div>
          </div>
          <div class="hero-metric-card hero-metric-card--circle">
            <el-progress
              type="circle"
              :percentage="pctNum(result.metrics.syntaxPassRate)"
              :color="rateColor(result.metrics.syntaxPassRate)"
              :stroke-width="7"
              :width="68"
            >
              <template #default="{ percentage }">
                <span class="circle-pct" :style="{ color: rateColor(result.metrics.syntaxPassRate) }">{{ percentage }}%</span>
              </template>
            </el-progress>
            <div class="hero-metric-label">语法通过率</div>
          </div>
        </div>
      </div>

      <!-- 8+4 Dashboard -->
      <div class="result-dashboard">
        <!-- 左侧 8 栏 -->
        <div class="dashboard-main">
          <ResultPanel :result="result" section="metrics" />
          <ChartPanel
            v-if="result.charts && result.charts.length"
            :charts="result.charts"
          />
          <!-- Agent 对话 -->
          <AgentChat
            :task-id="taskId"
            :result="result"
            :parent-task-id="parentTaskId"
            :parent-result="parentResult"
            @refine-started="(id) => router.push(`/task/${id}`)"
          />
        </div>

        <!-- 右侧 4 栏 -->
        <div class="dashboard-side">
          <!-- Agent 质量审视 -->
          <el-card v-if="result.reflectionSummary" class="side-card side-card--reflection">
            <template #header>
              <span class="side-card-title">◈ Agent 质量审视</span>
            </template>
            <div class="reflection-quote">
              <span class="reflection-bar"></span>
              <span class="reflection-text">{{ result.reflectionSummary }}</span>
            </div>
          </el-card>

          <!-- 风险提示 -->
          <el-card v-if="result.qualityWarnings && result.qualityWarnings.length" class="side-card side-card--warnings">
            <template #header>
              <span class="side-card-title side-card-title--warn">⚠ 风险提示</span>
            </template>
            <div class="warnings-list">
              <div v-for="(w, i) in result.qualityWarnings" :key="i" class="warning-item">
                <span class="warning-dot"></span>
                <span class="warning-text">{{ w }}</span>
              </div>
            </div>
          </el-card>

          <!-- 下一步建议 -->
          <el-card v-if="result.nextStepSuggestions && result.nextStepSuggestions.length" class="side-card side-card--suggestions">
            <template #header>
              <span class="side-card-title side-card-title--info">→ 下一步建议</span>
            </template>
            <div class="suggestions-chips">
              <el-tag
                v-for="(s, i) in result.nextStepSuggestions"
                :key="i"
                type="primary"
                effect="plain"
                class="suggestion-chip"
              >{{ s }}</el-tag>
            </div>
          </el-card>

          <!-- 处理成果 -->
          <ResultPanel :result="result" section="files" />

          <!-- 执行日志 -->
          <ExecutionTimeline
            :logs="result.executionLogs || []"
            :is-running="false"
            :current-skill="''"
          />
        </div>
      </div>

      <div class="new-task-cta">
        <el-button type="primary" size="large" @click="router.push('/')">
          + 开启新任务
        </el-button>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getTaskStatus, confirmSchema, getTaskResult, subscribeProgress } from '../api/task'
import SchemaConfirmDialog from '../components/SchemaConfirmDialog.vue'
import ResultPanel from '../components/ResultPanel.vue'
import ChartPanel from '../components/ChartPanel.vue'
import AgentChat from '../components/AgentChat.vue'
import ExecutionTimeline from '../components/ExecutionTimeline.vue'

const route = useRoute()
const router = useRouter()
const taskId = Number(route.params.taskId)

const status = ref({})
const result = ref(null)
const parentTaskId = ref(null)
const parentResult = ref(null)
const confirming = ref(false)
const elapsedSeconds = ref(0)
let elapsedTimer = null

const liveExecutionLogs = ref([])
const currentSkill = ref('')
let sseEmitter = null

const LONG_RUNNING_THRESHOLD = 120
const showLongRunningHint = computed(() =>
  elapsedSeconds.value >= LONG_RUNNING_THRESHOLD &&
  !TERMINAL.includes(status.value.taskStatus)
)

const displayProgress = ref(0)
let rafId = null
let progressTarget = 0
let progressSpeed = 0
let lastFrameTime = null

function startProgressLoop() {
  if (rafId) return
  lastFrameTime = null
  const step = (now) => {
    if (lastFrameTime === null) {
      lastFrameTime = now
      rafId = requestAnimationFrame(step)
      return
    }
    const elapsed = (now - lastFrameTime) / 1000
    lastFrameTime = now
    const remaining = progressTarget - displayProgress.value
    if (remaining <= 0.05) {
      displayProgress.value = progressTarget
      rafId = null
      return
    }
    displayProgress.value = Math.min(
      displayProgress.value + progressSpeed * elapsed,
      progressTarget
    )
    rafId = requestAnimationFrame(step)
  }
  rafId = requestAnimationFrame(step)
}

function setTargetProgress(realPct, isTerminal) {
  if (isTerminal) {
    if (rafId) { cancelAnimationFrame(rafId); rafId = null }
    displayProgress.value = realPct
    return
  }
  const target = Math.min(realPct, 95)
  const gap = target - displayProgress.value
  if (gap <= 0) return
  progressTarget = target
  progressSpeed = Math.max(gap / 1.8, 3)
  startProgressLoop()
}

let pollTimer = null
const TERMINAL = ['FINISHED', 'FAILED']

const isRunning = computed(() =>
  !!status.value.taskStatus &&
  !TERMINAL.includes(status.value.taskStatus) &&
  status.value.taskStatus !== 'WAITING_CONFIRM'
)

const statusTagType = computed(() => {
  const s = status.value.taskStatus
  if (s === 'FINISHED') return 'success'
  if (s === 'FAILED') return 'danger'
  if (s === 'WAITING_CONFIRM') return 'warning'
  return 'info'
})

const progressStatus = computed(() => {
  if (status.value.taskStatus === 'FINISHED') return 'success'
  if (status.value.taskStatus === 'FAILED') return 'exception'
  return ''
})

function statusLabel(s) {
  const map = {
    INIT: '初始化', SCHEMA_DETECTING: 'Schema 识别中', WAITING_CONFIRM: '等待确认',
    PREPROCESSING: '预处理中', ANALYZING: '分析中', VISUALIZING: '可视化中',
    FINISHED: '已完成', FAILED: '执行失败',
  }
  return map[s] || s || '-'
}

function stepLabel(step) {
  const map = {
    load_dataset: '加载数据集', normalize_code_text: '代码文本规范化',
    extract_function_structure: 'AST 函数结构提取', filter_invalid_samples: '过滤无效样本',
    filter_low_quality_docstring: '过滤低质量文档', deduplicate_samples: '样本去重',
    rename_variables_augmentation: '变量重命名增强', build_instruction_pairs: '构造指令样本对',
    compute_dataset_profile: '计算数据画像', evaluate_data_quality: '质量评估',
    generate_chart_specs: '生成图表配置', schema_confirm: '等待字段确认',
  }
  return step ? (map[step] || step) : (status.value.taskStatus === 'FINISHED' ? '全部完成' : '等待中...')
}

function fmt(val) {
  if (val == null) return '-'
  return val.toLocaleString()
}
function pctNum(val) {
  if (val == null) return 0
  return Math.round(val * 100)
}
function rateColor(val) {
  if (val == null) return '#909399'
  if (val >= 0.8) return '#67c23a'
  if (val >= 0.5) return '#e6a23c'
  return '#f56c6c'
}

async function poll() {
  try {
    const res = await getTaskStatus(taskId)
    status.value = res.data
    const isTerminal = TERMINAL.includes(res.data.taskStatus)
    setTargetProgress(res.data.progress || 0, isTerminal)
    if (res.data.taskStatus === 'FINISHED') {
      stopPoll()
      const r = await getTaskResult(taskId)
      result.value = r.data
      parentTaskId.value = res.data.parentTaskId || null
      if (res.data.parentTaskId) {
        try {
          const pr = await getTaskResult(res.data.parentTaskId)
          parentResult.value = pr.data
        } catch (e) {
          console.error('fetch parent result error', e)
        }
      }
    } else if (res.data.taskStatus === 'FAILED') {
      stopPoll()
    }
  } catch (e) {
    console.error('poll error', e)
  }
}

function handleProgressEvent(event) {
  const { event: evtType, skillName, progress, inputCount, outputCount, durationMs } = event
  if (progress != null) setTargetProgress(progress, evtType === 'task_done')
  if (evtType === 'skill_start') {
    currentSkill.value = skillName || ''
    if (!TERMINAL.includes(status.value.taskStatus)) {
      status.value = { ...status.value, taskStatus: 'PREPROCESSING' }
    }
  } else if (evtType === 'skill_done') {
    currentSkill.value = ''
    if (skillName) {
      liveExecutionLogs.value.push({
        skillName,
        status: 'success',
        inputCount: inputCount || 0,
        outputCount: outputCount || 0,
        durationMs: durationMs || 0,
      })
    }
  } else if (evtType === 'task_done') {
    currentSkill.value = ''
    stopSse()
    // 不直接 fetchResult，让 poll() 检测到 FINISHED 后自然拉取，避免数据库写入竞争
  } else if (evtType === 'task_error') {
    currentSkill.value = ''
    stopSse()
    status.value = { ...status.value, taskStatus: 'FAILED', errorMessage: event.message || '任务执行失败' }
  }
}

function startSse() {
  if (sseEmitter) return
  sseEmitter = subscribeProgress(taskId, handleProgressEvent, (err) => {
    console.warn('SSE error', err)
  })
}

function stopSse() {
  if (sseEmitter) { sseEmitter.close(); sseEmitter = null }
}

function startPoll() {
  poll()
  pollTimer = setInterval(poll, 2000)
  elapsedTimer = setInterval(() => { elapsedSeconds.value++ }, 1000)
}
function stopPoll() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
  if (elapsedTimer) { clearInterval(elapsedTimer); elapsedTimer = null }
}

async function handleConfirm(fields) {
  if (confirming.value) return
  confirming.value = true
  try { await confirmSchema(taskId, fields) } catch (e) { console.error('confirm error', e) }
  finally { confirming.value = false }
}

onMounted(() => { startPoll(); startSse() })
onUnmounted(() => {
  stopPoll()
  stopSse()
  if (rafId) { cancelAnimationFrame(rafId); rafId = null }
})
</script>

<style scoped>
.task-page {
  max-width: 1300px;
  margin: 0 auto;
  padding: 0 20px;
}

.page-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 20px;
  padding-top: 4px;
}

.back-btn { flex-shrink: 0; }

.page-title-group {
  display: flex;
  align-items: center;
  gap: 12px;
}

.page-title {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  color: #1a1f2e;
}

.task-id-accent { color: #409eff; }

.status-tag-wrap {
  display: flex;
  align-items: center;
  gap: 6px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.dot-finished { background: #67c23a; }
.dot-failed { background: #f56c6c; }
.dot-waiting_confirm { background: #e6a23c; }
.dot-preprocessing, .dot-analyzing, .dot-visualizing, .dot-schema_detecting {
  background: #409eff;
  animation: pulse 1.5s infinite;
}
.dot-init { background: #c0c4cc; }

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.status-card { margin-bottom: 16px; }

.status-body {
  display: flex;
  align-items: center;
  gap: 24px;
}

.status-info { flex: 1; }

.status-step-label {
  font-size: 11px;
  color: #9ca3af;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 4px;
}

.status-step-name {
  font-size: 15px;
  font-weight: 600;
  color: #1a1f2e;
}

.status-progress-wrap {
  flex: 2;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.progress-pct {
  font-size: 12px;
  color: #409eff;
  font-weight: 600;
  text-align: right;
}

.status-progress { width: 100%; }
.fail-alert { margin-top: 14px; }
.long-running-alert { margin-top: 10px; }
.confirm-card { margin-bottom: 16px; }

.status-bar-compact {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 8px 16px;
  background: #fff;
  border: 1px solid #e8eaed;
  border-radius: 8px;
  margin-bottom: 16px;
}

.status-bar-step {
  font-size: 12px;
  color: #67c23a;
  font-weight: 600;
  flex-shrink: 0;
}

.status-bar-right {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  justify-content: flex-end;
}

.status-bar-pct {
  font-size: 12px;
  color: #67c23a;
  font-weight: 600;
  flex-shrink: 0;
}

.status-bar-progress { width: 160px; }

/* 全宽 Hero */
.result-hero { margin-bottom: 20px; }

.hero-banner {
  background: linear-gradient(135deg, #1a6fd4 0%, #409eff 100%);
  border-radius: 8px 8px 0 0;
  padding: 16px 24px;
}

.hero-banner-inner {
  display: flex;
  align-items: center;
  gap: 14px;
}

.hero-icon {
  width: 34px;
  height: 34px;
  background: rgba(255,255,255,0.2);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 17px;
  font-weight: 700;
  flex-shrink: 0;
}

.hero-title {
  color: #fff;
  font-size: 16px;
  font-weight: 700;
  line-height: 1.3;
}

.hero-sub {
  color: rgba(255,255,255,0.85);
  font-size: 13px;
  margin-top: 2px;
}

.hero-metrics {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  border: 1px solid #e8eaed;
  border-top: none;
  border-radius: 0 0 8px 8px;
  overflow: hidden;
}

.hero-metric-card {
  padding: 16px 18px;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  background: #fff;
  border-right: 1px solid #f0f2f5;
}

.hero-metric-card:last-child { border-right: none; }
.hero-metric-card--primary { background: #f0f7ff; }
.hero-metric-card--circle { padding: 14px 12px; gap: 8px; }

.hero-metric-value {
  font-size: 26px;
  font-weight: 700;
  color: #1a1f2e;
  line-height: 1.2;
}

.hero-metric-value--blue { color: #409eff; }

.circle-pct {
  font-size: 14px;
  font-weight: 700;
}

.hero-metric-label {
  font-size: 12px;
  color: #909399;
}

@media (max-width: 700px) {
  .hero-metrics { grid-template-columns: repeat(2, 1fr); }
  .hero-metric-card { border-bottom: 1px solid #f0f2f5; }
}

/* 8+4 Dashboard */
.result-dashboard {
  display: grid;
  grid-template-columns: 8fr 4fr;
  gap: 20px;
  align-items: start;
  margin-bottom: 20px;
}

@media (max-width: 1100px) {
  .result-dashboard { grid-template-columns: 1fr; }
}

.dashboard-main,
.dashboard-side {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
}

/* 右侧卡片 */
.side-card-title {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
}

.side-card-title--warn { color: #e6a23c; }
.side-card-title--info { color: #409eff; }

.side-card--reflection {
  border-left: 3px solid #409eff !important;
}

.reflection-quote {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.reflection-bar {
  width: 3px;
  background: #409eff;
  border-radius: 2px;
  flex-shrink: 0;
  align-self: stretch;
  min-height: 20px;
}

.reflection-text {
  font-size: 13px;
  color: #303133;
  line-height: 1.7;
}

.side-card--warnings {
  border-left: 3px solid #e6a23c !important;
}

:deep(.side-card--warnings .el-card__body) {
  background: #fdf6ec;
}

.warnings-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.warning-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 13px;
  color: #7a5c00;
  line-height: 1.5;
}

.warning-dot {
  width: 6px;
  height: 6px;
  background: #e6a23c;
  border-radius: 50%;
  flex-shrink: 0;
  margin-top: 5px;
}

.warning-text { flex: 1; }

.suggestions-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.suggestion-chip {
  white-space: normal;
  height: auto;
  line-height: 1.5;
  padding: 4px 10px;
  font-size: 12px;
}

.new-task-cta {
  display: flex;
  justify-content: center;
  padding: 24px 0 32px;
}
</style>
