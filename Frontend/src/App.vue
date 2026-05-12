<template>
  <el-config-provider>
    <div class="app-shell">
      <header class="app-nav">
        <div class="nav-inner">
          <div class="nav-brand">
            <span class="nav-icon">◈</span>
            <span class="nav-title">DataProcess Agent</span>
            <span class="nav-sub">代码数据预处理工作台</span>
          </div>
          <div v-if="currentTaskId" class="nav-task">
            <span class="nav-task-label">当前任务</span>
            <span class="nav-task-id">#{{ currentTaskId }}</span>
          </div>
        </div>
      </header>
      <main class="app-main">
        <Transition name="page-fade" mode="out-in">
          <router-view :key="$route.fullPath" />
        </Transition>
      </main>
    </div>
  </el-config-provider>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const currentTaskId = computed(() => route.params.taskId || null)
</script>

<style>
* { box-sizing: border-box; }

body {
  margin: 0;
  background: #f0f2f5;
  font-family: 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
  color: #1a1f2e;
}

.app-shell {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.app-nav {
  height: 52px;
  background: #1a1f2e;
  border-bottom: 1px solid #2d3548;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25);
  position: sticky;
  top: 0;
  z-index: 100;
  flex-shrink: 0;
}

.nav-inner {
  max-width: 1340px;
  margin: 0 auto;
  height: 100%;
  padding: 0 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.nav-brand {
  display: flex;
  align-items: center;
  gap: 10px;
}

.nav-icon {
  color: #409eff;
  font-size: 18px;
  line-height: 1;
}

.nav-title {
  color: #ffffff;
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 0.3px;
}

.nav-sub {
  color: #5a6478;
  font-size: 12px;
  padding-left: 10px;
  border-left: 1px solid #2d3548;
  margin-left: 2px;
}

.nav-task {
  display: flex;
  align-items: center;
  gap: 6px;
}

.nav-task-label {
  color: #5a6478;
  font-size: 12px;
}

.nav-task-id {
  color: #409eff;
  font-size: 13px;
  font-weight: 600;
  background: rgba(64, 158, 255, 0.1);
  padding: 2px 8px;
  border-radius: 4px;
  border: 1px solid rgba(64, 158, 255, 0.2);
}

.app-main {
  flex: 1;
  padding: 32px 0 48px;
}

/* 全局卡片样式覆盖 */
.el-card {
  border: 1px solid #e8eaed !important;
  border-radius: 8px !important;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06) !important;
}

.el-card__header {
  padding: 14px 20px !important;
  border-bottom: 1px solid #f0f2f5 !important;
  font-size: 13px !important;
  font-weight: 600 !important;
  color: #303133 !important;
}

.el-card__body {
  padding: 20px !important;
}

/* 全局按钮微调 */
.el-button--primary {
  background: #409eff !important;
  border-color: #409eff !important;
}

.el-button--primary:hover {
  background: #337ecc !important;
  border-color: #337ecc !important;
}

/* 进度条 */
.el-progress-bar__outer {
  border-radius: 4px !important;
}

.el-progress-bar__inner {
  border-radius: 4px !important;
}

/* 页面切换淡入淡出 */
.page-fade-enter-active,
.page-fade-leave-active {
  transition: opacity 0.15s ease;
}

.page-fade-enter-from,
.page-fade-leave-to {
  opacity: 0;
}
</style>
