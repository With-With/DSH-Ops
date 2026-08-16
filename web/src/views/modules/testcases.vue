<template>
  <div class="module-page">
    <el-card shadow="never" class="main-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">用例管理</span>
        </div>
      </template>
      <el-empty description="模块建设中：由任务集流水线产出的测试用例（matrix 行）将在此统一管理与维护">
        <el-text type="info" size="small">规划：用例列表 / 数据驱动行 / 用例与任务集关联 / 评审后固化</el-text>
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
