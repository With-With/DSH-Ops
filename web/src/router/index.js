import { createRouter, createWebHistory } from 'vue-router'
import Layout from '@/layout/index.vue'

const routes = [
  {
    path: '/',
    component: Layout,
    redirect: '/runtimes',
    children: [
      {
        path: 'runtimes',
        name: 'Runtimes',
        component: () => import('@/views/runtimes/index.vue'),
        meta: { title: '运行时管理', icon: 'Cpu' },
      },
      {
        path: 'recorder',
        name: 'Recorder',
        component: () => import('@/views/recorder/index.vue'),
        meta: { title: '录制中心', icon: 'VideoCamera' },
      },
      {
        path: 'replay',
        name: 'Replay',
        component: () => import('@/views/replay/index.vue'),
        meta: { title: '回放中心', icon: 'VideoPlay' },
      },
      {
        path: 'assets',
        name: 'Assets',
        component: () => import('@/views/assets/index.vue'),
        meta: { title: '元素仓', icon: 'Picture' },
      },
      {
        path: 'tasksets',
        name: 'TaskSets',
        component: () => import('@/views/tasksets/index.vue'),
        meta: { title: '任务集', icon: 'Collection' },
      },
      {
        path: 'reviews',
        name: 'Reviews',
        component: () => import('@/views/placeholders/P2.vue'),
        meta: { title: '评审收件箱', icon: 'Message', phase: 'P2' },
      },
      {
        path: 'ai-config',
        name: 'AiConfig',
        component: () => import('@/views/placeholders/P3.vue'),
        meta: { title: 'AI 配置', icon: 'MagicStick', phase: 'P3' },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
