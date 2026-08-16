<template>
  <el-container class="ph-container">
    <el-result
      :icon="iconName"
      :title="`${phaseName} 阶段建设中`"
      :sub-title="`「${route.meta.title}」模块将在 ${phaseName} 阶段上线，敬请期待。`"
    >
      <template #extra>
        <el-button type="primary" @click="$router.push('/runtimes')">返回运行时管理</el-button>
      </template>
    </el-result>
  </el-container>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const phase = computed(() => route.meta.phase || 'P1')
const phaseName = computed(() => {
  const map = { P1: 'P1', P2: 'P2', P3: 'P3' }
  return map[phase.value] || 'P1'
})
const iconName = computed(() => {
  return 'Loading'
})
</script>

<style scoped>
.ph-container {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
