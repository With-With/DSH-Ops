<template>
  <el-container class="layout-container">
    <!-- 侧边栏 -->
    <el-aside :width="sidebarWidth" class="layout-aside">
      <Sidebar :collapsed="collapsed" />
    </el-aside>

    <el-container>
      <!-- 头部 -->
      <el-header class="layout-header">
        <HeaderBar
          :collapsed="collapsed"
          @toggle-collapse="toggleCollapse"
        />
      </el-header>

      <!-- 主内容区 -->
      <el-main class="layout-main">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, computed } from 'vue'
import Sidebar from './Sidebar.vue'
import HeaderBar from './HeaderBar.vue'

const collapsed = ref(false)

const sidebarWidth = computed(() =>
  collapsed.value ? 'var(--do-sidebar-width-collapsed)' : 'var(--do-sidebar-width)'
)

function toggleCollapse() {
  collapsed.value = !collapsed.value
}
</script>

<style scoped>
.layout-container {
  height: 100vh;
  width: 100%;
}

.layout-aside {
  background-color: var(--do-sidebar-bg);
  transition: width var(--do-transition-base);
  overflow: hidden;
}

.layout-header {
  background-color: var(--do-header-bg);
  border-bottom: 1px solid var(--do-header-border);
  padding: 0 20px;
  height: var(--do-header-height) !important;
  display: flex;
  align-items: center;
  box-shadow: var(--do-shadow-light);
  z-index: 10;
}

.layout-main {
  background-color: var(--do-bg);
  padding: 20px;
  overflow-y: auto;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
