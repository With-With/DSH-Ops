<template>
  <div class="module-page">
    <el-card shadow="never" class="main-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">套件管理</span>
        </div>
      </template>
      <el-empty description="模块建设中：用例按场景/模块组织成套件，支持夜间回归编排">
        <el-text type="info" size="small">规划：套件 CRUD / 用例编排 / 回归计划（夜间零 LLM 依赖）</el-text>
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
