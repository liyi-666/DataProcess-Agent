<template>
  <el-card class="chat-card">
    <template #header>
      <div class="chat-header">
        <span class="chat-header-dot"></span>
        <span class="chat-header-title">智能问答</span>
      </div>
    </template>

    <div ref="scrollRef" class="chat-messages">
      <div v-if="messages.length === 0" class="chat-empty">
        <div class="chat-empty-icon">◈</div>
        <div class="chat-empty-text">可以询问任务执行情况、数据质量、处理策略等</div>
      </div>

      <div v-for="(msg, i) in messages" :key="i" class="chat-msg-row" :class="msg.role === 'user' ? 'chat-msg-row--user' : 'chat-msg-row--agent'">
        <div v-if="msg.role !== 'user'" class="chat-avatar chat-avatar--agent">◈</div>
        <div class="chat-bubble" :class="msg.role === 'user' ? 'chat-bubble--user' : 'chat-bubble--agent'">
          {{ msg.content }}
        </div>
        <div v-if="msg.role === 'user'" class="chat-avatar chat-avatar--user">我</div>
      </div>

      <div v-if="sending" class="chat-msg-row chat-msg-row--agent">
        <div class="chat-avatar chat-avatar--agent">◈</div>
        <div class="chat-bubble chat-bubble--agent chat-bubble--typing">
          <span class="typing-dot"></span>
          <span class="typing-dot"></span>
          <span class="typing-dot"></span>
        </div>
      </div>
    </div>

    <div class="chat-input-row">
      <el-input
        v-model="input"
        placeholder="输入问题，按 Enter 发送..."
        class="chat-input"
        @keyup.enter="send"
      />
      <el-button type="primary" :loading="sending" class="chat-send-btn" @click="send">发送</el-button>
    </div>
  </el-card>
</template>

<script setup>
import { ref, nextTick } from 'vue'
import { sendChatMessage } from '../api/task'

const props = defineProps({
  taskId: { type: Number, required: true },
})

const messages = ref([])
const input = ref('')
const sending = ref(false)
const scrollRef = ref(null)

async function send() {
  const text = input.value.trim()
  if (!text) return
  messages.value.push({ role: 'user', content: text })
  input.value = ''
  sending.value = true
  await nextTick()
  scrollToBottom()
  try {
    const res = await sendChatMessage(props.taskId, text)
    messages.value.push({ role: 'agent', content: res.data.reply })
  } catch (e) {
    messages.value.push({ role: 'agent', content: '请求失败: ' + e.message })
  } finally {
    sending.value = false
    await nextTick()
    scrollToBottom()
  }
}

function scrollToBottom() {
  if (scrollRef.value) {
    scrollRef.value.scrollTop = scrollRef.value.scrollHeight
  }
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
}

.chat-header-title {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
}

.chat-messages {
  height: 260px;
  overflow-y: auto;
  padding: 4px 0;
  margin-bottom: 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.chat-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 10px;
}

.chat-empty-icon {
  font-size: 28px;
  color: #c0c4cc;
}

.chat-empty-text {
  font-size: 13px;
  color: #c0c4cc;
  text-align: center;
}

.chat-msg-row {
  display: flex;
  align-items: flex-end;
  gap: 8px;
}

.chat-msg-row--user {
  flex-direction: row-reverse;
}

.chat-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  flex-shrink: 0;
}

.chat-avatar--agent {
  background: #1a1f2e;
  color: #409eff;
  font-size: 13px;
}

.chat-avatar--user {
  background: #409eff;
  color: #fff;
}

.chat-bubble {
  max-width: 75%;
  padding: 9px 12px;
  border-radius: 10px;
  font-size: 13px;
  line-height: 1.6;
  word-break: break-word;
}

.chat-bubble--agent {
  background: #f5f7fa;
  color: #303133;
  border-bottom-left-radius: 3px;
}

.chat-bubble--user {
  background: #409eff;
  color: #fff;
  border-bottom-right-radius: 3px;
}

.chat-bubble--typing {
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

.typing-dot:nth-child(2) {
  animation-delay: 0.2s;
}

.typing-dot:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes typing-bounce {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
  30% { transform: translateY(-4px); opacity: 1; }
}

.chat-input-row {
  display: flex;
  gap: 8px;
}

.chat-input {
  flex: 1;
}

.chat-send-btn {
  flex-shrink: 0;
}
</style>
