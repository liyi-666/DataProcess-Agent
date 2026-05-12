<template>
  <el-card class="schema-card">
    <!-- Agent 需要确认 Banner -->
    <div class="confirm-banner">
      <div class="confirm-banner-icon">?</div>
      <div class="confirm-banner-text">
        <div class="confirm-banner-title">Agent 需要你的确认</div>
        <div class="confirm-banner-sub">{{ confirmPayload.message }}</div>
      </div>
      <el-tag
        v-if="confirmPayload.confidenceLevel"
        :type="confidenceLevelTag(confirmPayload.confidenceLevel)"
        class="confidence-tag"
      >
        置信度 {{ confidenceLevelLabel(confirmPayload.confidenceLevel) }}
      </el-tag>
    </div>

    <!-- Agent 判断依据 -->
    <div v-if="confirmPayload.whyNeedUserConfirm || confirmPayload.recommendationReason" class="reasoning-block">
      <div class="reasoning-bar"></div>
      <div class="reasoning-content">
        <div v-if="confirmPayload.whyNeedUserConfirm" class="reasoning-row">
          <span class="reasoning-key">原因</span>
          <span class="reasoning-val">{{ confirmPayload.whyNeedUserConfirm }}</span>
        </div>
        <div v-if="confirmPayload.recommendationReason" class="reasoning-row">
          <span class="reasoning-key">推荐依据</span>
          <span class="reasoning-val">{{ confirmPayload.recommendationReason }}</span>
        </div>
      </div>
    </div>

    <!-- 字段选择 -->
    <div class="fields-section">
      <div class="fields-title">字段映射</div>

      <div class="field-row">
        <div class="field-label">
          <span class="field-required">*</span> 代码字段
        </div>
        <el-select v-model="form.codeField" placeholder="请选择" class="field-select">
          <el-option v-for="f in confirmPayload.candidateCodeFields" :key="f" :label="f" :value="f">
            <span>{{ f }}</span>
            <el-tag v-if="f === confirmPayload.recommendedCodeField" type="success" size="small" class="option-recommend-tag">推荐</el-tag>
          </el-option>
        </el-select>
        <div v-if="form.codeField === confirmPayload.recommendedCodeField" class="field-hint field-hint--ok">
          ✓ 与 Agent 推荐一致
        </div>
      </div>

      <div class="field-row">
        <div class="field-label">文档字段</div>
        <el-select v-model="form.docstringField" placeholder="请选择（可选）" clearable class="field-select">
          <el-option v-for="f in confirmPayload.candidateDocstringFields" :key="f" :label="f" :value="f">
            <span>{{ f }}</span>
            <el-tag v-if="f === confirmPayload.recommendedDocstringField" type="success" size="small" class="option-recommend-tag">推荐</el-tag>
          </el-option>
        </el-select>
      </div>

      <div class="field-row">
        <div class="field-label">语言字段</div>
        <el-select v-model="form.languageField" placeholder="请选择（可选）" clearable class="field-select">
          <el-option v-for="f in confirmPayload.candidateLanguageFields" :key="f" :label="f" :value="f">
            <span>{{ f }}</span>
            <el-tag v-if="f === confirmPayload.recommendedLanguageField" type="success" size="small" class="option-recommend-tag">推荐</el-tag>
          </el-option>
        </el-select>
      </div>
    </div>

    <!-- 确认按钮 -->
    <div class="confirm-action">
      <el-button
        type="warning"
        :disabled="!form.codeField"
        class="confirm-btn"
        @click="submit"
      >
        确认字段，继续处理 →
      </el-button>
    </div>
  </el-card>
</template>

<script setup>
import { reactive, onMounted } from 'vue'

const props = defineProps({
  confirmPayload: { type: Object, required: true },
})
const emit = defineEmits(['confirm'])

const form = reactive({
  codeField: '',
  docstringField: '',
  languageField: '',
})

onMounted(() => {
  const p = props.confirmPayload
  form.codeField = p.recommendedCodeField || p.candidateCodeFields?.[0] || ''
  form.docstringField = p.recommendedDocstringField || p.candidateDocstringFields?.[0] || ''
  form.languageField = p.recommendedLanguageField || p.candidateLanguageFields?.[0] || ''
})

function submit() {
  emit('confirm', { ...form })
}

function confidenceLevelTag(level) {
  if (level === 'high') return 'success'
  if (level === 'medium') return 'warning'
  return 'danger'
}

function confidenceLevelLabel(level) {
  if (level === 'high') return '高'
  if (level === 'medium') return '中'
  return '低'
}
</script>

<style scoped>
.confirm-banner {
  display: flex;
  align-items: center;
  gap: 14px;
  background: linear-gradient(135deg, #fff7e6 0%, #fffbe6 100%);
  border: 1px solid #f5dab1;
  border-radius: 8px;
  padding: 16px 18px;
  margin-bottom: 16px;
}

.confirm-banner-icon {
  width: 36px;
  height: 36px;
  background: #f5a623;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 18px;
  font-weight: 700;
  flex-shrink: 0;
}

.confirm-banner-text {
  flex: 1;
  min-width: 0;
}

.confirm-banner-title {
  font-size: 14px;
  font-weight: 700;
  color: #1a1f2e;
  margin-bottom: 3px;
}

.confirm-banner-sub {
  font-size: 13px;
  color: #606266;
  line-height: 1.5;
}

.confidence-tag {
  flex-shrink: 0;
}

.reasoning-block {
  display: flex;
  gap: 10px;
  background: #f0f7ff;
  border-radius: 6px;
  padding: 12px 14px;
  margin-bottom: 20px;
}

.reasoning-bar {
  width: 3px;
  background: #409eff;
  border-radius: 2px;
  flex-shrink: 0;
}

.reasoning-content {
  flex: 1;
  min-width: 0;
}

.reasoning-row {
  display: flex;
  gap: 8px;
  font-size: 13px;
  margin-bottom: 6px;
  line-height: 1.5;
}

.reasoning-row:last-child {
  margin-bottom: 0;
}

.reasoning-key {
  color: #409eff;
  font-weight: 600;
  flex-shrink: 0;
  min-width: 56px;
}

.reasoning-val {
  color: #303133;
}

.fields-title {
  font-size: 13px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 14px;
}

.field-row {
  margin-bottom: 14px;
}

.field-label {
  font-size: 13px;
  color: #606266;
  margin-bottom: 6px;
}

.field-required {
  color: #f56c6c;
  margin-right: 2px;
}

.field-select {
  width: 100%;
}

.field-hint {
  font-size: 12px;
  margin-top: 4px;
}

.field-hint--ok {
  color: #67c23a;
}

.option-recommend-tag {
  margin-left: 8px;
}

.confirm-action {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid #f0f2f5;
}

.confirm-btn {
  width: 100%;
  height: 40px;
  font-size: 14px;
  font-weight: 600;
}
</style>
