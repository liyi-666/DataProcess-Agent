<template>
  <el-card class="agent-chat-card">
    <template #header>
      <div class="chat-header">
        <span class="chat-header-dot"></span>
        <span class="chat-header-title">与 Agent 对话</span>
        <span class="chat-header-sub">可询问执行情况，也可描述优化目标</span>
      </div>
    </template>

    <div ref="scrollRef" class="chat-messages">
      <template v-for="(msg, i) in messages" :key="i">
        <!-- 用户消息 -->
        <div v-if="msg.role === 'user'" class="msg-row msg-row--user">
          <div class="bubble bubble--user">{{ msg.content }}</div>
          <div class="avatar avatar--user">我</div>
        </div>

        <!-- Agent 文字解释 -->
        <div v-else-if="msg.type === 'text'" class="msg-row msg-row--agent">
          <div class="avatar avatar--agent">◈</div>
          <div class="bubble bubble--agent">{{ msg.content }}</div>
        </div>

        <!-- Agent 澄清 -->
        <div v-else-if="msg.type === 'clarify'" class="msg-row msg-row--agent">
          <div class="avatar avatar--agent">◈</div>
          <div class="bubble bubble--clarify">
            <div class="clarify-label">需要更多信息</div>
            <div class="clarify-body">{{ msg.content }}</div>
          </div>
        </div>

        <!-- Agent 意图卡片（rerun_with_options） -->
        <div v-else-if="msg.type === 'intent'" class="msg-row msg-row--agent msg-row--wide">
          <div class="avatar avatar--agent">◈</div>
          <div class="intent-card">
            <div class="intent-header">
              <span class="intent-label">◈ Agent 的理解</span>
              <el-tag size="small" :type="confidenceTagType(msg.action.confidence)">
                置信度 {{ msg.action.confidence }}
              </el-tag>
              <el-tag v-if="msg.action.optimizationGoal" size="small" type="primary">
                {{ goalLabel(msg.action.optimizationGoal) }}
              </el-tag>
            </div>
            <div class="intent-summary">{{ msg.action.intentSummary }}</div>
            <div v-if="msg.action.strategyReason?.length" class="detail-block detail-strategy">
              <div class="detail-title">策略依据</div>
              <div v-for="(r, j) in msg.action.strategyReason" :key="j" class="detail-item">· {{ r }}</div>
            </div>
            <div v-if="msg.action.expectedImpact?.length" class="detail-block detail-impact">
              <div class="detail-title">预期影响</div>
              <div v-for="(imp, j) in msg.action.expectedImpact" :key="j" class="detail-item">· {{ imp }}</div>
            </div>
            <div v-if="msg.action.riskWarnings?.length" class="detail-block detail-risk">
              <div class="detail-title">风险提示</div>
              <div v-for="(w, j) in msg.action.riskWarnings" :key="j" class="detail-item">⚠ {{ w }}</div>
            </div>
            <div v-if="hasChanges(msg.action)" class="detail-block detail-changes">
              <div class="detail-title">本轮改动</div>
              <div v-for="(val, key) in msg.action.optionsDiff" :key="key" class="detail-item">
                · {{ optionLabel(key) }}：{{ formatOptionVal(val) }}
              </div>
              <div v-if="msg.action.filterRelax">
                <div v-for="(val, key) in msg.action.filterRelax" :key="key" class="detail-item">
                  · {{ filterRelaxLabel(key) }}：放宽至 {{ val }}
                </div>
              </div>
            </div>
            <div class="intent-actions">
              <el-button
                v-if="!msg.confirmed"
                type="warning"
                size="small"
                :loading="msg.running"
                @click="handleRefineRun(msg)"
              >确认，启动新一轮 →</el-button>
              <span v-else class="confirmed-hint">✓ 已启动新一轮</span>
            </div>
          </div>
        </div>

        <!-- Agent 对比消息 -->
        <div v-else-if="msg.type === 'compare'" class="msg-row msg-row--agent msg-row--wide">
          <div class="avatar avatar--agent">◈</div>
          <div class="compare-msg">
            <div class="compare-msg-header">
              <span class="intent-label">◈ 轮次对比</span>
              <span v-if="parentTaskId" class="compare-subtitle">任务 #{{ parentTaskId }} → #{{ taskId }}</span>
              <span v-else class="compare-no-parent">当前是第一轮，没有上一轮可对比</span>
            </div>
            <ComparePanel
              v-if="parentTaskId"
              :task-id="taskId"
              :other-task-id="parentTaskId"
              :current-metrics="result?.metrics"
              :previous-metrics="parentResult?.metrics"
              class="compare-inline"
            />
          </div>
        </div>
      </template>

      <!-- 打字中 -->
      <div v-if="sending" class="msg-row msg-row--agent">
        <div class="avatar avatar--agent">◈</div>
        <div class="bubble bubble--agent bubble--typing">
          <span class="typing-dot"></span>
          <span class="typing-dot"></span>
          <span class="typing-dot"></span>
        </div>
      </div>
    </div>

    <div v-if="messages.length === 0" class="chat-suggested-bar">
      <span class="chat-suggested-label">试试问 Agent：</span>
      <div class="chat-suggested">
        <button
          v-for="q in SUGGESTED"
          :key="q"
          class="suggested-chip"
          @click="sendSuggested(q)"
        >{{ q }}</button>
      </div>
    </div>

    <div class="chat-input-row">
      <el-input
        v-model="input"
        placeholder="输入问题或优化目标，按 Enter 发送..."
        class="chat-input"
        @keyup.enter="send"
      />
      <el-button type="primary" :loading="sending" class="chat-send-btn" @click="send">发送</el-button>
    </div>
  </el-card>
</template>

<script setup>
import { ref, nextTick } from 'vue'
import { parseIntent, sendChatMessage, refineRun } from '../api/task'
import ComparePanel from './ComparePanel.vue'

const props = defineProps({
  taskId: { type: Number, required: true },
  result: { type: Object, default: null },
  parentTaskId: { type: Number, default: null },
  parentResult: { type: Object, default: null },
})

const emit = defineEmits(['refine-started'])

const messages = ref([])
const input = ref('')
const sending = ref(false)
const scrollRef = ref(null)

const SUGGESTED = [
  '为什么保留率这么低？',
  '哪一步过滤最多？',
  '为什么 AST 失败这么多？',
  '帮我提高保留率',
  '对比一下上一轮',
]

async function sendSuggested(q) {
  input.value = q
  await send()
}

async function send() {
  const text = input.value.trim()
  if (!text || sending.value) return
  messages.value.push({ role: 'user', type: 'text', content: text })
  input.value = ''
  sending.value = true
  await nextTick()
  scrollToBottom()

  try {
    const metrics = props.result?.metrics || null
    const options = props.result?.options || null
    const summary = props.result?.summary || ''
    const reflectionSummary = props.result?.reflectionSummary || ''

    const intentRes = await parseIntent(props.taskId, text, metrics, options, summary, reflectionSummary)
    const action = intentRes.data?.refinementAction || null
    const actionType = action?.actionType

    if (actionType === 'explain' || !action) {
      const chatRes = await sendChatMessage(
        props.taskId, text, metrics, props.result?.executionLogs || [], summary
      )
      messages.value.push({ role: 'agent', type: 'text', content: chatRes.data?.reply || '（无回复）' })
    } else if (actionType === 'clarify') {
      const clarifyText = action.clarificationNeeded || action.intentSummary || '需要更多信息。'
      messages.value.push({ role: 'agent', type: 'clarify', content: clarifyText })
    } else if (actionType === 'compare') {
      messages.value.push({ role: 'agent', type: 'compare', action })
    } else {
      messages.value.push({ role: 'agent', type: 'intent', action, confirmed: false, running: false })
    }
  } catch (e) {
    messages.value.push({ role: 'agent', type: 'text', content: '请求失败: ' + e.message })
  } finally {
    sending.value = false
    await nextTick()
    scrollToBottom()
  }
}

async function handleRefineRun(msg) {
  if (msg.confirmed || msg.running) return
  msg.running = true
  try {
    const res = await refineRun(props.taskId, msg.action)
    const newTaskId = res.data?.taskId
    if (newTaskId) {
      msg.confirmed = true
      emit('refine-started', newTaskId)
    }
  } catch (e) {
    messages.value.push({ role: 'agent', type: 'text', content: '启动失败: ' + e.message })
  } finally {
    msg.running = false
  }
}

function scrollToBottom() {
  if (scrollRef.value) scrollRef.value.scrollTop = scrollRef.value.scrollHeight
}

function confidenceTagType(c) {
  if (c === 'high') return 'success'
  if (c === 'medium') return 'warning'
  return 'danger'
}

function hasChanges(action) {
  return (action.optionsDiff && Object.keys(action.optionsDiff).length > 0) ||
    (action.filterRelax && Object.keys(action.filterRelax).length > 0)
}

function optionLabel(key) {
  const map = {
    enableDedup: '精确去重', enableAstDedup: 'AST 结构去重',
    enableAstExtract: 'AST 函数提取', enableAugmentation: '变量重命名增强',
    enableInstructionPairs: '指令对构造',
  }
  return map[key] || key
}

function formatOptionVal(val) { return val === true ? '开启' : val === false ? '关闭' : String(val) }
function filterRelaxLabel(key) { return key === 'docstringMinLen' ? 'docstring 最短长度' : key }

function goalLabel(goal) {
  const map = {
    maximize_retention: '最大化保留率', maximize_quality: '最大化数据质量',
    balance_retain_and_quality: '平衡保留率与质量', training_data_construction: '训练数据构造',
    reduce_noise: '减少噪声/去重', data_augmentation: '数据增强', compare_rounds: '对比两轮',
  }
  return map[goal] || goal
}
</script>

<style scoped>
.chat-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.chat-header-dot {
  width: 8px;
  height: 8px;
  background: #67c23a;
  border-radius: 50%;
  flex-shrink: 0;
}

.chat-header-title {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
}

.chat-header-sub {
  font-size: 12px;
  color: #909399;
}

.chat-messages {
  height: 320px;
  overflow-y: auto;
  padding: 4px 0;
  margin-bottom: 12px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.chat-suggested-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  padding: 8px 0 6px;
  border-top: 1px solid #f0f2f5;
}

.chat-suggested-label {
  font-size: 12px;
  color: #909399;
  flex-shrink: 0;
}

.chat-suggested {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.suggested-chip {
  background: #f0f7ff;
  border: 1px solid #b3d8ff;
  border-radius: 16px;
  padding: 5px 12px;
  font-size: 12px;
  color: #409eff;
  cursor: pointer;
  transition: background 0.15s;
  line-height: 1.4;
}

.suggested-chip:hover {
  background: #e0efff;
}

/* 消息行 */
.msg-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.msg-row--user {
  flex-direction: row-reverse;
}

.msg-row--wide {
  align-items: flex-start;
}

.avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  flex-shrink: 0;
  margin-top: 2px;
}

.avatar--agent {
  background: #1a1f2e;
  color: #409eff;
  font-size: 13px;
}

.avatar--user {
  background: #409eff;
  color: #fff;
}

/* 气泡 */
.bubble {
  max-width: 75%;
  padding: 9px 12px;
  border-radius: 10px;
  font-size: 13px;
  line-height: 1.6;
  word-break: break-word;
}

.bubble--agent {
  background: #f5f7fa;
  color: #303133;
  border-bottom-left-radius: 3px;
}

.bubble--user {
  background: #409eff;
  color: #fff;
  border-bottom-right-radius: 3px;
}

.bubble--clarify {
  background: #fdf6ec;
  border: 1px solid #f5dab1;
  border-bottom-left-radius: 3px;
  max-width: 85%;
}

.clarify-label {
  font-size: 12px;
  font-weight: 600;
  color: #e6a23c;
  margin-bottom: 6px;
}

.clarify-body {
  font-size: 13px;
  color: #7a5c00;
  line-height: 1.6;
  white-space: pre-line;
}

.bubble--typing {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 12px 14px;
}

.typing-dot {
  width: 6px;
  height: 6px;
  background: #909399;
  border-radius: 50%;
  animation: typing-bounce 1.2s infinite;
}

.typing-dot:nth-child(2) { animation-delay: 0.2s; }
.typing-dot:nth-child(3) { animation-delay: 0.4s; }

@keyframes typing-bounce {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
  30% { transform: translateY(-4px); opacity: 1; }
}

/* 意图卡片 */
.intent-card {
  flex: 1;
  padding: 14px 16px;
  background: #e8f4ff;
  border: 1px solid #b3d8ff;
  border-radius: 10px;
  border-bottom-left-radius: 3px;
  border-left: 3px solid #409eff;
  min-width: 0;
}

.intent-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}

.intent-label {
  font-size: 13px;
  font-weight: 700;
  color: #1a6fc4;
}

.intent-summary {
  font-size: 13px;
  color: #303133;
  line-height: 1.7;
  margin-bottom: 10px;
}

.detail-block {
  font-size: 12px;
  border-radius: 6px;
  padding: 8px 10px;
  margin-bottom: 8px;
}

.detail-title {
  font-weight: 600;
  margin-bottom: 4px;
  color: #303133;
}

.detail-item {
  margin-bottom: 2px;
  line-height: 1.5;
}

.detail-strategy { background: #fff; color: #606266; }
.detail-impact { background: #f6ffed; border: 1px solid #b7eb8f; color: #389e0d; }
.detail-risk { background: #fffbe6; border: 1px solid #ffe58f; color: #8c6e00; }
.detail-changes { background: #fff; color: #606266; }

.intent-actions {
  margin-top: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.confirmed-hint {
  font-size: 13px;
  color: #67c23a;
  font-weight: 600;
}

/* 对比消息 */
.compare-msg {
  flex: 1;
  min-width: 0;
}

.compare-msg-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.compare-subtitle {
  font-size: 12px;
  color: #909399;
  background: #f5f7fa;
  padding: 2px 8px;
  border-radius: 4px;
}

.compare-no-parent {
  font-size: 12px;
  color: #e6a23c;
}

.compare-inline {
  /* ComparePanel 内部已有样式，这里只控制外边距 */
  margin-top: 0;
}

/* 输入区 */
.chat-input-row {
  display: flex;
  gap: 8px;
}

.chat-input { flex: 1; }
.chat-send-btn { flex-shrink: 0; }
</style>
