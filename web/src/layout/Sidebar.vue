<template>
  <div class="sidebar">
    <!-- Logo 区 -->
    <div class="sidebar-logo">
      <span v-if="!collapsed" class="logo-text">DSH-Ops</span>
      <el-icon v-else :size="24" color="#fff"><Cpu /></el-icon>
    </div>

    <!-- 菜单 -->
    <el-menu
      :default-active="activeMenu"
      :collapse="collapsed"
      :collapse-transition="false"
      router
      background-color="var(--do-sidebar-bg)"
      text-color="var(--do-sidebar-text)"
      active-text-color="var(--do-sidebar-text-active)"
      class="sidebar-menu"
    >
      <template v-for="item in menuTree" :key="item.key">
        <!-- 分组子菜单 -->
        <el-sub-menu v-if="item.children" :index="item.key">
          <template #title>
            <el-icon><component :is="item.icon" /></el-icon>
            <span>{{ item.title }}</span>
          </template>
          <el-menu-item
            v-for="child in item.children"
            :key="child.path"
            :index="child.path"
          >
            <el-icon><component :is="child.icon" /></el-icon>
            <template #title><span>{{ child.title }}</span></template>
          </el-menu-item>
        </el-sub-menu>
        <!-- 普通菜单项 -->
        <el-menu-item v-else :index="item.path">
          <el-icon><component :is="item.icon" /></el-icon>
          <template #title>
            <span>{{ item.title }}</span>
            <el-tag
              v-if="item.phase"
              :type="phaseTagType(item.phase)"
              size="small"
              class="phase-tag"
            >{{ item.phase }}</el-tag>
          </template>
        </el-menu-item>
      </template>
    </el-menu>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

defineProps({
  collapsed: {
    type: Boolean,
    default: false,
  },
})

const route = useRoute()

const menuTree = [
  { key: 'runtimes', path: '/runtimes', title: '运行时管理', icon: 'Cpu' },
  { key: 'assets', path: '/assets', title: '元素仓', icon: 'Picture' },
  { key: 'tasksets', path: '/tasksets', title: '任务集', icon: 'Collection' },
  { key: 'reviews', path: '/reviews', title: '评审中心', icon: 'Message' },
  { key: 'ai-config', path: '/ai-config', title: 'AI 配置', icon: 'MagicStick' },
  // P4：观测中心分组（概览 + 录制 + 回放）
  {
    key: 'obs-group',
    title: '观测中心',
    icon: 'DataLine',
    children: [
      { path: '/obs', title: '观测概览', icon: 'DataAnalysis' },
      { path: '/obs/recorder', title: '录制中心', icon: 'VideoCamera' },
      { path: '/obs/replay', title: '回放中心', icon: 'VideoPlay' },
    ],
  },
]

const activeMenu = computed(() => route.path)

function phaseTagType(phase) {
  const map = { P1: 'success', P2: 'warning', P3: 'info' }
  return map[phase] || 'info'
}
</script>

<style scoped>
.sidebar {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.sidebar-logo {
  height: var(--do-header-height);
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #2b3b51;
  border-bottom: 1px solid #1f2d3d;
  color: #fff;
  font-weight: 600;
  font-size: 18px;
  letter-spacing: 1px;
  flex-shrink: 0;
}

.logo-text {
  background: linear-gradient(90deg, #409eff, #67c23a);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.sidebar-menu {
  border-right: none;
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
}

.sidebar-menu:not(.el-menu--collapse) .el-menu-item {
  min-width: 220px;
}

.phase-tag {
  margin-left: 6px;
}
</style>
