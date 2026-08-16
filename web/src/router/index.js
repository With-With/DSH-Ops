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
        meta: { title: '配置中心', icon: 'Cpu' },
      },
      {
        path: 'assets',
        name: 'Assets',
        component: () => import('@/views/assets/index.vue'),
        meta: { title: '元素管理', icon: 'Picture', group: 'UI自动化测试' },
      },
      {
        path: 'tasksets',
        name: 'TaskSets',
        component: () => import('@/views/tasksets/index.vue'),
        meta: { title: '任务集', icon: 'Collection', group: 'UI自动化测试' },
      },
      {
        path: 'reviews',
        name: 'Reviews',
        component: () => import('@/views/reviews/index.vue'),
        meta: { title: '评审中心', icon: 'Message', group: 'UI自动化测试' },
      },
      {
        path: 'ai-config',
        name: 'AiConfig',
        component: () => import('@/views/ai-config/index.vue'),
        meta: { title: 'AI 配置', icon: 'MagicStick' },
      },
      // 观测中心分组：概览 + 录制 + 回放
      {
        path: 'obs',
        name: 'ObsOverview',
        component: () => import('@/views/obs/index.vue'),
        meta: { title: '观测概览', icon: 'DataLine', group: '观测中心' },
      },
      {
        path: 'obs/recorder',
        name: 'ObsRecorder',
        component: () => import('@/views/recorder/index.vue'),
        meta: { title: '录制中心', icon: 'VideoCamera', group: '观测中心' },
      },
      {
        path: 'obs/replay',
        name: 'ObsReplay',
        component: () => import('@/views/replay/index.vue'),
        meta: { title: '回放中心', icon: 'VideoPlay', group: '观测中心' },
      },
      // UI自动化测试：用例/套件/执行记录/报告（P5 骨架占位）
      {
        path: 'testcases',
        name: 'TestCases',
        component: () => import('@/views/modules/testcases.vue'),
        meta: { title: '用例管理', icon: 'Document', group: 'UI自动化测试' },
      },
      {
        path: 'suites',
        name: 'Suites',
        component: () => import('@/views/modules/suites.vue'),
        meta: { title: '套件管理', icon: 'Folder', group: 'UI自动化测试' },
      },
      {
        path: 'executions',
        name: 'Executions',
        component: () => import('@/views/modules/executions.vue'),
        meta: { title: '执行记录', icon: 'Timer', group: 'UI自动化测试' },
      },
      {
        path: 'reports',
        name: 'Reports',
        component: () => import('@/views/modules/reports.vue'),
        meta: { title: '报告管理', icon: 'DataBoard', group: 'UI自动化测试' },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
