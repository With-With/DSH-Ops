<template>
  <div class="header-bar">
    <div class="header-left">
      <!-- 折叠按钮 -->
      <div class="collapse-btn" @click="$emit('toggle-collapse')">
        <el-icon :size="20">
          <Fold v-if="!collapsed" />
          <Expand v-else />
        </el-icon>
      </div>

      <!-- 面包屑 -->
      <el-breadcrumb separator="/">
        <el-breadcrumb-item
          v-for="(item, index) in breadcrumbs"
          :key="index"
          :to="item.path ? { path: item.path } : undefined"
        >
          {{ item.title }}
        </el-breadcrumb-item>
      </el-breadcrumb>
    </div>

    <div class="header-right">
      <!-- 主题切换 -->
      <el-tooltip :content="themeTip" placement="bottom">
        <el-button
          class="theme-toggle"
          circle
          @click="toggleTheme"
        >
          <el-icon :size="18">
            <Sunny v-if="themeStore.mode === 'dark'" />
            <Moon v-else />
          </el-icon>
        </el-button>
      </el-tooltip>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useThemeStore } from '@/stores/theme'

defineProps({
  collapsed: {
    type: Boolean,
    default: false,
  },
})

defineEmits(['toggle-collapse'])

const route = useRoute()
const themeStore = useThemeStore()

const breadcrumbs = computed(() => {
  return [
    { title: '首页', path: '/' },
    { title: route.meta.title || '未知' },
  ]
})

const themeTip = computed(() =>
  themeStore.mode === 'dark' ? '切换到亮色模式' : '切换到暗色模式'
)

function toggleTheme() {
  themeStore.toggle()
}
</script>

<style scoped>
.header-bar {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.collapse-btn {
  cursor: pointer;
  color: var(--do-fg);
  display: flex;
  align-items: center;
  padding: 4px;
  border-radius: 4px;
  transition: background-color var(--do-transition-base);
}

.collapse-btn:hover {
  background-color: var(--do-border-light);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.theme-toggle {
  border: none;
  background: transparent;
  color: var(--do-fg-secondary);
}

.theme-toggle:hover {
  background-color: var(--do-border-light);
  color: var(--do-primary);
}
</style>
