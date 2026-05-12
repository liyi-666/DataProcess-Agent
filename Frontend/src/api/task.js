import axios from 'axios'

const http = axios.create({ baseURL: '/api' })

http.interceptors.response.use(
  (res) => res.data,
  (err) => Promise.reject(err)
)

export function uploadTask(file, taskName, taskDescription) {
  const form = new FormData()
  form.append('file', file)
  if (taskName) form.append('taskName', taskName)
  if (taskDescription) form.append('taskDescription', taskDescription)
  return http.post('/tasks/upload', form)
}

export function planTask(taskId) {
  return http.post(`/tasks/${taskId}/plan`)
}

export function runTask(taskId, options) {
  return http.post(`/tasks/${taskId}/run`, { options })
}

export function getTaskStatus(taskId) {
  return http.get(`/tasks/${taskId}/status`)
}

export function confirmSchema(taskId, fields) {
  return http.post(`/tasks/${taskId}/confirm-schema`, fields)
}

export function getTaskResult(taskId) {
  return http.get(`/tasks/${taskId}/result`)
}

export function sendChatMessage(taskId, message, metrics, executionLogs, summary) {
  return http.post('/chat/send', { taskId, message, metrics, executionLogs, summary })
}

export function downloadFile(fileId) {
  window.open(`/api/files/${fileId}/download`, '_blank')
}

export function parseIntent(taskId, userMessage, currentMetrics, currentOptions, summary, reflectionSummary) {
  return http.post(`/tasks/${taskId}/refine/parse`, {
    userMessage,
    currentMetrics,
    currentOptions,
    summary,
    reflectionSummary,
  })
}

export function refineRun(taskId, refinementAction) {
  return http.post(`/tasks/${taskId}/refine/run`, { refinementAction })
}

export function compareRounds(taskId, otherTaskId) {
  return http.get(`/tasks/${taskId}/compare/${otherTaskId}`)
}

export function subscribeProgress(taskId, onEvent, onError) {
  const es = new EventSource(`/api/tasks/${taskId}/progress`)
  es.onmessage = (e) => {
    try { onEvent(JSON.parse(e.data)) } catch (err) { console.warn('SSE parse error', err, e.data) }
  }
  es.onerror = onError
  return es
}
