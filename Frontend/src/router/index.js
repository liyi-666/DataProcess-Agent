import { createRouter, createWebHistory } from 'vue-router'
import UploadView from '../views/UploadView.vue'
import TaskView from '../views/TaskView.vue'

const routes = [
  { path: '/', component: UploadView },
  { path: '/task/:taskId', component: TaskView },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
