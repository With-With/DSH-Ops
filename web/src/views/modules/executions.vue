<template>
  <div class="module-page">
    <el-card shadow="never" class="main-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">执行记录</span>
        </div>
      </template>
      <el-empty description="模块建设中：任务集流水线 / 套件回归的执行历史与 trace/视频 归档">
        <el-text type="info" size="small">规划：执行列表 / 结果统计 / trace 与视频回看 / 失败重试</el-text>
      </el-empty>
    </el-card>
  </div>
</template>

<script setup>
</script>

<style scoped>
.module-page { height: 100%; }
.main-card { height: 100%; border-radius: 8px; }
.card-header { display: flex; align-items: center; justify-content: space-between; }
.card-title { font-size: 16px; font-weight: 600; color: var(--do-fg); }
</style>
