<template>
  <div class="upload-page">

    <!-- Phase 1: 上传 -->
    <template v-if="phase === 'upload'">
      <div class="page-hero">
        <div class="hero-badge">Agent 工作台</div>
        <h1 class="hero-title">代码数据预处理 Agent</h1>
        <p class="hero-sub">上传数据集，Agent 自动分析结构并推荐最优处理策略</p>
      </div>

      <div class="upload-layout">
        <el-card class="upload-card">
          <template #header>
            <span class="card-header-icon">📋</span> 任务信息
          </template>
          <el-form label-width="90px" class="compact-form">
            <el-form-item label="任务名称">
              <el-input v-model="taskName" placeholder="可选，留空自动生成" />
            </el-form-item>
            <el-form-item label="任务描述">
              <el-input v-model="taskDescription" type="textarea" :rows="2" placeholder="可选，描述你的处理目标" />
            </el-form-item>
          </el-form>
        </el-card>

        <el-card class="upload-card">
          <template #header>
            <span class="card-header-icon">📁</span> 上传数据集
          </template>
          <el-upload
            class="dataset-uploader"
            :auto-upload="false"
            :limit="1"
            :on-change="onFileChange"
            :on-remove="onFileRemove"
            accept=".json,.jsonl,.parquet,.csv"
            drag
          >
            <div class="upload-inner">
              <div class="upload-icon">⬆</div>
              <div class="upload-text">拖拽文件到此处，或 <em>点击选择</em></div>
              <div class="upload-hint">支持 jsonl / parquet / csv / json</div>
            </div>
          </el-upload>
        </el-card>

        <el-button
          class="start-btn"
          type="primary"
          :loading="uploading || planning"
          :disabled="!selectedFile"
          @click="handleUploadAndPlan"
        >
          <span v-if="uploading">上传中...</span>
          <span v-else-if="planning">Agent 分析中...</span>
          <span v-else>上传并分析 →</span>
        </el-button>
      </div>
    </template>

    <!-- Phase 2: Agent 分析结果 -->
    <template v-if="phase === 'plan'">

      <!-- Agent 分析完成横幅 -->
      <div class="agent-banner">
        <span class="banner-check">✓</span>
        <span class="banner-text">Agent 已完成数据集分析</span>
        <span class="banner-dot">·</span>
        <span class="banner-mode">推荐模式：{{ modeLabel(planResult.recommendedMode) }}</span>
      </div>

      <div class="plan-layout">

        <!-- 推荐模式卡片（最高权重） -->
        <div class="mode-card" :class="'mode-' + planResult.recommendedMode">
          <div class="mode-card-left">
            <div class="mode-label-row">
              <span class="mode-icon">◈</span>
              <span class="mode-section-title">Agent 推荐模式</span>
            </div>
            <div class="mode-name">{{ modeLabel(planResult.recommendedMode) }}</div>
            <div v-if="planResult.recommendationReason" class="mode-reason">
              {{ planResult.recommendationReason }}
            </div>
          </div>
          <div class="mode-card-right">
            <el-tag :type="modeTagType(planResult.recommendedMode)" size="large" class="mode-tag">
              {{ planResult.recommendedMode || 'standard' }}
            </el-tag>
          </div>
        </div>

        <!-- 数据集特征 -->
        <el-card v-if="planResult.observedDatasetTraits?.length" class="traits-card">
          <template #header>
            <span class="card-header-icon">👁</span>
            Agent 观察到的数据特征
          </template>
          <div class="traits-grid">
            <div
              v-for="(t, i) in planResult.observedDatasetTraits"
              :key="i"
              class="trait-chip"
              :class="'trait-chip--' + traitType(t)"
            >
              <span class="trait-dot"></span>
              {{ t }}
            </div>
          </div>
        </el-card>

        <!-- 处理策略决策 + 风险提示 两列 -->
        <div class="strategy-risk-row">

          <!-- 处理策略决策 -->
          <el-card class="strategy-card">
            <template #header>
              <span class="card-header-icon">⚡</span>
              处理策略决策
            </template>
            <div class="strategy-list">
              <div
                v-for="item in strategyDefs"
                :key="item.key"
                class="strategy-item"
                :class="options[item.key] ? 'strategy-on' : 'strategy-off'"
              >
                <span class="strategy-dot"></span>
                <span class="strategy-label">{{ item.label }}</span>
                <span v-if="options[item.key]" class="strategy-badge">推荐</span>
              </div>
            </div>
          </el-card>

          <!-- 风险提示 -->
          <el-card v-if="planResult.riskWarnings?.length" class="risk-card">
            <template #header>
              <span class="card-header-icon risk-icon">⚠</span>
              风险提示
            </template>
            <div class="risk-list">
              <div
                v-for="(w, i) in planResult.riskWarnings"
                :key="i"
                class="risk-item"
              >
                <span class="risk-bullet">⚠</span>
                {{ w }}
              </div>
            </div>
          </el-card>

          <!-- 无风险时占位 -->
          <el-card v-else class="risk-card risk-card-empty">
            <template #header>
              <span class="card-header-icon">✓</span>
              风险检测
            </template>
            <div class="risk-ok">
              <span class="risk-ok-icon">✓</span>
              未检测到明显风险
            </div>
          </el-card>
        </div>

        <!-- 系统执行流程 -->
        <el-card class="pipeline-card">
          <template #header>
            <div class="pipeline-header">
              <span class="card-header-icon">⚙</span>
              系统执行流程
              <span class="header-sub">基于 Agent 推荐，可通过高级设置调整</span>
              <div class="pipeline-legend">
                <span class="legend-item"><span class="legend-dot legend-dot--on"></span>执行</span>
                <span class="legend-item"><span class="legend-dot legend-dot--off"></span>跳过</span>
                <span class="legend-item"><span class="legend-dot legend-dot--override"></span>已调整</span>
              </div>
            </div>
          </template>
          <div class="pipeline-steps">
            <div
              v-for="(stage, i) in systemPipeline"
              :key="i"
              class="pipeline-step"
              :class="{
                'pipeline-step--off': !stage.active,
                'pipeline-step--override': stage.userOverride,
              }"
            >
              <div
                class="step-num"
                :class="{
                  'step-num--off': !stage.active,
                  'step-num--override': stage.userOverride,
                }"
              >{{ i + 1 }}</div>
              <div class="step-name">{{ stage.label }}</div>
              <div v-if="stage.userOverride && stage.active" class="step-tag step-tag--added" title="已在推荐基础上添加">+</div>
              <div v-else-if="stage.userOverride && !stage.active" class="step-tag step-tag--removed" title="已在推荐基础上移除">−</div>
              <div v-else-if="!stage.active" class="step-skip">跳过</div>
              <div v-if="i < systemPipeline.length - 1" class="step-arrow">→</div>
            </div>
          </div>
        </el-card>

        <!-- 高级设置 -->
        <el-card class="advanced-card">
          <template #header>
            <div class="advanced-header" @click="showAdvanced = !showAdvanced">
              <div class="advanced-header-left">
                <span class="card-header-icon">🔧</span>
                高级设置
                <span class="advanced-summary">已启用 {{ enabledStrategies.length }} / {{ strategyDefs.length }} 项策略</span>
              </div>
              <span class="advanced-toggle" :class="{ open: showAdvanced }">▾</span>
            </div>
          </template>
          <div v-show="showAdvanced" class="advanced-body">
            <div class="advanced-hint">已根据 Agent 推荐预填充，可按需微调</div>
            <div class="advanced-switches">
              <div v-for="item in strategyDefs" :key="item.key" class="switch-row">
                <div class="switch-info">
                  <span class="switch-label">{{ item.label }}</span>
                  <span class="switch-desc">{{ item.desc }}</span>
                </div>
                <el-switch v-model="options[item.key]" />
              </div>
            </div>
          </div>
          <div v-show="!showAdvanced" class="advanced-collapsed">
            点击展开，在 Agent 推荐基础上手动微调
          </div>
        </el-card>

        <!-- 执行说明 + 按钮 -->
        <div class="action-area">
          <div class="action-hint">
            Agent 将按以上策略开始处理，预计耗时取决于数据集大小
          </div>
          <div class="action-buttons">
            <el-button class="back-btn" @click="phase = 'upload'">← 重新上传</el-button>
            <el-button class="run-btn" type="primary" :loading="running" @click="handleRun">
              确认并启动处理 →
            </el-button>
          </div>
        </div>

      </div>
    </template>

    <el-alert
      v-if="errorMsg"
      class="error-alert"
      :title="errorMsg"
      type="error"
      :closable="false"
    />
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { uploadTask, planTask, runTask } from '../api/task'

const router = useRouter()

const phase = ref('upload')
const taskName = ref('')
const taskDescription = ref('')
const selectedFile = ref(null)
const taskId = ref(null)
const planResult = ref({})
const uploading = ref(false)
const planning = ref(false)
const running = ref(false)
const errorMsg = ref('')
const showAdvanced = ref(false)

const options = ref({
  enableDedup: true,
  enableAstDedup: true,
  enableAstExtract: true,
  enableAugmentation: false,
  enableInstructionPairs: true,
})

// Agent 推荐的初始配置，用于在流程图中标注"推荐"vs"用户修改"
const recommendedOptions = ref({})

const PIPELINE_STAGES = [
  { label: '数据加载',   optionKey: null },
  { label: '样本规范化', optionKey: null },
  { label: '结构提取',   optionKey: 'enableAstExtract' },
  { label: '样本过滤',   optionKey: null },
  { label: '精确去重',       optionKey: 'enableDedup' },
  { label: 'AST 去重',   optionKey: 'enableAstDedup' },
  { label: '数据增强',   optionKey: 'enableAugmentation' },
  { label: '指令对构造', optionKey: 'enableInstructionPairs' },
  { label: '分析可视化', optionKey: null },
  { label: '结果导出',   optionKey: null },
]

const systemPipeline = computed(() =>
  PIPELINE_STAGES.map(s => {
    const active = s.optionKey === null || options.value[s.optionKey]
    const hasRec = s.optionKey !== null && s.optionKey in recommendedOptions.value
    const recActive = hasRec ? recommendedOptions.value[s.optionKey] : active
    // 偏离推荐 = 有推荐基线且当前值与推荐不同
    const userOverride = hasRec && active !== recActive
    return { label: s.label, active, recActive, userOverride }
  })
)

const strategyDefs = [
  { key: 'enableDedup',            label: '精确去重',     desc: '基于代码哈希去除完全重复样本' },
  { key: 'enableAstDedup',         label: 'AST 结构去重', desc: '基于语法树结构去除等价代码' },
  { key: 'enableAstExtract',       label: 'AST 函数提取', desc: '提取函数名、参数、返回注解' },
  { key: 'enableAugmentation',     label: '变量重命名增强', desc: '通过变量重命名扩充训练样本' },
  { key: 'enableInstructionPairs', label: '生成指令对',   desc: '构造 docstring→code 训练样本对' },
]

const enabledStrategies  = computed(() => strategyDefs.filter(s => options.value[s.key]))
const disabledStrategies = computed(() => strategyDefs.filter(s => !options.value[s.key]))

function onFileChange(file) { selectedFile.value = file.raw }
function onFileRemove() { selectedFile.value = null }

async function handleUploadAndPlan() {
  errorMsg.value = ''
  uploading.value = true
  try {
    const res = await uploadTask(selectedFile.value, taskName.value, taskDescription.value)
    taskId.value = res.data.taskId
  } catch (e) {
    errorMsg.value = '上传失败: ' + (e.response?.data?.message || e.message)
    return
  } finally {
    uploading.value = false
  }

  planning.value = true
  try {
    const res = await planTask(taskId.value)
    planResult.value = res.data
    const rec = res.data.recommendedOptions
    if (rec) {
      if (rec.enableDedup != null) options.value.enableDedup = rec.enableDedup
      if (rec.enableAstDedup != null) options.value.enableAstDedup = rec.enableAstDedup
      if (rec.enableAstExtract != null) options.value.enableAstExtract = rec.enableAstExtract
      if (rec.enableAugmentation != null) options.value.enableAugmentation = rec.enableAugmentation
      if (rec.enableInstructionPairs != null) options.value.enableInstructionPairs = rec.enableInstructionPairs
      // 保存推荐基线，用于流程图标注
      recommendedOptions.value = { ...options.value }
    }
    phase.value = 'plan'
  } catch (e) {
    errorMsg.value = '分析失败: ' + (e.response?.data?.message || e.message)
  } finally {
    planning.value = false
  }
}

async function handleRun() {
  errorMsg.value = ''
  running.value = true
  try {
    const optionsSnapshot = { ...options.value }
    console.log('[handleRun] sending options:', JSON.stringify(optionsSnapshot))
    await runTask(taskId.value, optionsSnapshot)
    router.push(`/task/${taskId.value}`)
  } catch (e) {
    errorMsg.value = '启动失败: ' + (e.response?.data?.message || e.message)
  } finally {
    running.value = false
  }
}

function traitType(trait) {
  const warn = ['未检测', '歧义', '受限', '非标准', '失败', '可能', '仅', '大幅']
  const ok = ['检测到代码字段', '检测到文档字段', '检测到语言字段', 'Parquet', '函数定义']
  if (warn.some(k => trait.includes(k))) return 'warning'
  if (ok.some(k => trait.includes(k))) return 'success'
  return 'info'
}

function modeLabel(mode) {
  const map = {
    cleaning_analysis: '基础清洗分析',
    training_data_construction: '训练数据构造',
    enhanced_construction: '增强构造模式',
  }
  return map[mode] || mode || '标准模式'
}

function modeTagType(mode) {
  if (mode === 'enhanced_construction') return 'danger'
  if (mode === 'training_data_construction') return 'warning'
  return 'info'
}
</script>

<style scoped>
.upload-page {
  max-width: 760px;
  margin: 0 auto;
  padding: 0 20px;
}

/* Hero */
.page-hero {
  text-align: center;
  padding: 40px 0 32px;
}

.hero-badge {
  display: inline-block;
  background: rgba(64, 158, 255, 0.1);
  color: #409eff;
  border: 1px solid rgba(64, 158, 255, 0.25);
  border-radius: 20px;
  padding: 3px 14px;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.5px;
  margin-bottom: 14px;
}

.hero-title {
  margin: 0 0 10px;
  font-size: 28px;
  font-weight: 700;
  color: #1a1f2e;
  letter-spacing: -0.3px;
}

.hero-sub {
  margin: 0;
  font-size: 14px;
  color: #6b7280;
  line-height: 1.6;
}

/* Upload layout */
.upload-layout {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.card-header-icon {
  margin-right: 6px;
}

.compact-form {
  margin-bottom: -8px;
}

.dataset-uploader :deep(.el-upload-dragger) {
  border: 2px dashed #d0d7de;
  border-radius: 8px;
  background: #fafbfc;
  transition: border-color 0.2s, background 0.2s, box-shadow 0.2s;
  width: 100%;
  height: auto;
  padding: 32px 20px;
}

.dataset-uploader :deep(.el-upload-dragger:hover) {
  border-color: #409eff;
  background: #f0f7ff;
}

.dataset-uploader :deep(.el-upload-dragger.is-dragover) {
  border-color: #409eff;
  border-style: solid;
  background: #e8f4ff;
  box-shadow: 0 0 0 3px rgba(64, 158, 255, 0.15);
}

.dataset-uploader :deep(.el-upload) {
  width: 100%;
}

.upload-inner {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.upload-icon {
  font-size: 32px;
  color: #409eff;
  line-height: 1;
}

.upload-text {
  font-size: 14px;
  color: #374151;
}

.upload-text em {
  color: #409eff;
  font-style: normal;
  font-weight: 600;
}

.upload-hint {
  font-size: 12px;
  color: #9ca3af;
}

.start-btn {
  width: 100%;
  height: 44px;
  font-size: 15px;
  font-weight: 600;
  border-radius: 8px !important;
  letter-spacing: 0.3px;
}

/* Plan layout */
.plan-layout {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding-bottom: 40px;
}

/* Agent 分析完成横幅 */
.agent-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 18px;
  background: linear-gradient(135deg, #f0f9ff 0%, #e8f4ff 100%);
  border: 1px solid #b3d8ff;
  border-radius: 8px;
  font-size: 13px;
  color: #1a6fc4;
  margin-bottom: 4px;
}

.banner-check {
  color: #67c23a;
  font-weight: 700;
  font-size: 15px;
}

.banner-text {
  font-weight: 600;
}

.banner-dot {
  color: #b3d8ff;
}

.banner-mode {
  color: #409eff;
  font-weight: 600;
}

/* 推荐模式卡片 */
.mode-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px;
  border-radius: 8px;
  border: 1px solid #e8eaed;
  background: #fff;
  border-left: 4px solid #f5a623;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}

.mode-card.mode-enhanced_construction {
  border-left-color: #f56c6c;
}

.mode-card.mode-cleaning_analysis {
  border-left-color: #409eff;
}

.mode-card-left {
  flex: 1;
}

.mode-label-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
}

.mode-icon {
  color: #f5a623;
  font-size: 14px;
}

.mode-section-title {
  font-size: 11px;
  font-weight: 700;
  color: #9ca3af;
  text-transform: uppercase;
  letter-spacing: 0.8px;
}

.mode-name {
  font-size: 20px;
  font-weight: 700;
  color: #1a1f2e;
  margin-bottom: 6px;
  letter-spacing: -0.2px;
}

.mode-reason {
  font-size: 13px;
  color: #6b7280;
  line-height: 1.5;
}

.mode-card-right {
  flex-shrink: 0;
  margin-left: 20px;
}

.mode-tag {
  font-size: 12px !important;
}

/* 数据集特征 */
.traits-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.trait-chip {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 500;
}

.trait-chip--info {
  background: #f0f9ff;
  border: 1px solid #b3d8ff;
  color: #1a6fc4;
}

.trait-chip--success {
  background: #f6ffed;
  border: 1px solid #b7eb8f;
  color: #389e0d;
}

.trait-chip--warning {
  background: #fffbe6;
  border: 1px solid #ffe58f;
  color: #7c5e00;
}

.trait-chip--info .trait-dot { background: #409eff; }
.trait-chip--success .trait-dot { background: #67c23a; }
.trait-chip--warning .trait-dot { background: #e6a23c; }

.trait-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

/* 策略 + 风险 两列 */
.strategy-risk-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.strategy-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.strategy-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  border-radius: 6px;
  font-size: 13px;
}

.strategy-on {
  background: #f6ffed;
  color: #303133;
}

.strategy-off {
  background: #fafafa;
  color: #9ca3af;
}

.strategy-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.strategy-on .strategy-dot { background: #67c23a; }
.strategy-off .strategy-dot { background: #dcdfe6; }

.strategy-label {
  flex: 1;
}

.strategy-badge {
  font-size: 10px;
  color: #67c23a;
  background: #f0fff4;
  border: 1px solid #b7eb8f;
  border-radius: 4px;
  padding: 1px 6px;
  font-weight: 600;
}

.risk-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.risk-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 10px;
  background: #fffbe6;
  border: 1px solid #ffe58f;
  border-radius: 6px;
  font-size: 13px;
  color: #7c5e00;
  line-height: 1.5;
}

.risk-bullet {
  flex-shrink: 0;
  color: #e6a23c;
}

.risk-icon {
  color: #e6a23c;
}

.risk-card {
  border-left: 3px solid #e6a23c !important;
}

.risk-ok {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #67c23a;
  padding: 8px 0;
}

.risk-ok-icon {
  font-size: 16px;
  font-weight: 700;
}

/* 系统执行流程 */
.header-sub {
  font-size: 11px;
  color: #9ca3af;
  font-weight: 400;
  margin-left: 8px;
}

.pipeline-steps {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0;
}

.pipeline-step {
  display: flex;
  align-items: center;
  gap: 6px;
}

.pipeline-step--off .step-name {
  color: #c0c4cc;
  text-decoration: line-through;
}

.pipeline-step--override .step-name {
  color: #f5a623;
}

.pipeline-header {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.pipeline-legend {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-left: auto;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: #909399;
  font-weight: normal;
}

.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.legend-dot--on {
  background: #409eff;
}

.legend-dot--off {
  background: #c0c4cc;
}

.legend-dot--override {
  background: #f5a623;
}

.step-skip {
  font-size: 10px;
  color: #c0c4cc;
  background: #f5f7fa;
  border: 1px solid #e4e7ed;
  border-radius: 3px;
  padding: 1px 4px;
}

.step-tag {
  font-size: 10px;
  font-weight: 700;
  border-radius: 3px;
  padding: 1px 5px;
  line-height: 1.4;
}

.step-tag--added {
  color: #67c23a;
  background: #f0f9eb;
  border: 1px solid #b3e19d;
}

.step-tag--removed {
  color: #f56c6c;
  background: #fef0f0;
  border: 1px solid #fbc4c4;
}

.step-num {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #409eff;
  color: #fff;
  font-size: 10px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.step-num--off {
  background: #c0c4cc;
}

.step-num--override {
  background: #f5a623;
}

.step-name {
  font-size: 12px;
  color: #374151;
  white-space: nowrap;
}

.step-arrow {
  color: #d0d7de;
  font-size: 12px;
  margin: 0 6px;
}

/* 高级设置 */
.advanced-card :deep(.el-card__header) {
  cursor: pointer;
  user-select: none;
}

.advanced-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.advanced-header-left {
  display: flex;
  align-items: center;
  gap: 6px;
}

.advanced-summary {
  font-size: 11px;
  color: #9ca3af;
  font-weight: 400;
  margin-left: 4px;
}

.advanced-toggle {
  color: #9ca3af;
  font-size: 14px;
  transition: transform 0.2s;
  display: inline-block;
}

.advanced-toggle.open {
  transform: rotate(180deg);
}

.advanced-hint {
  font-size: 12px;
  color: #9ca3af;
  margin-bottom: 14px;
  padding: 8px 12px;
  background: #f9fafb;
  border-radius: 6px;
}

.advanced-switches {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.switch-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-radius: 6px;
  transition: background 0.15s;
}

.switch-row:hover {
  background: #f9fafb;
}

.switch-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.switch-label {
  font-size: 13px;
  color: #303133;
  font-weight: 500;
}

.switch-desc {
  font-size: 11px;
  color: #9ca3af;
}

.advanced-collapsed {
  font-size: 12px;
  color: #c0c4cc;
  padding: 4px 0;
}

/* 执行按钮区 */
.action-area {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.action-hint {
  text-align: center;
  font-size: 12px;
  color: #9ca3af;
}

.action-buttons {
  display: flex;
  gap: 12px;
}

.back-btn {
  flex-shrink: 0;
}

.run-btn {
  flex: 1;
  height: 44px;
  font-size: 15px;
  font-weight: 600;
  border-radius: 8px !important;
}

/* 错误提示 */
.error-alert {
  margin-top: 16px;
}
</style>
