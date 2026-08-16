<template>
  <el-container class="ph-container">
    <el-result
      icon="Loading"
      :title="`${phase} 阶段建设中`"
      :sub-title="`「${route.meta.title}」模块将在 ${phase} 阶段上线，敬请期待。`"
    >
      <template #extra>
        <el-button type="primary" @click="$router.push('/runtimes')">返回运行时管理</el-button>
      </template>
    </el-result>
  </el-container>
</template>

<script setup>
import { useRoute } from 'vue-router'

const route = useRoute()
const phase = 'P3'
</script>

<style scoped>
.ph-container {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
