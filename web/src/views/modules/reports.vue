<template>
  <div class="module-page">
    <el-card shadow="never" class="main-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">报告管理</span>
        </div>
      </template>
      <el-empty description="模块建设中：执行结果汇总为可视化报告（趋势/通过率/失败分布）">
        <el-text type="info" size="small">规划：报告生成 / 趋势图表 / 导出与分享</el-text>
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
