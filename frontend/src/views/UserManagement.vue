<template>
  <div class="user-management-container">
    <el-tabs
      v-model="activeTab"
      class="user-management-tabs"
    >
      <el-tab-pane label="用户统计" name="stats" />
      <el-tab-pane label="客服管理" name="k-users" />
    </el-tabs>

    <div class="user-management-body">
      <router-view />
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

const activeTab = ref('stats')

function syncFromRoute() {
  const name = (route.name || '').toString()
  if (name === 'CustomerService') {
    activeTab.value = 'k-users'
  } else {
    activeTab.value = 'stats'
  }
}

// activeTab 变化（点击 tab）→ 同步推路由；路由变化 → 同步 activeTab
// 双 watch 互相同步，彻底脱离 element-plus 事件回调的细节差异
watch(activeTab, (val) => {
  const target = val === 'k-users'
    ? '/user-management/k-users'
    : '/user-management/stats'
  if (route.path !== target) {
    router.push(target)
  }
})

onMounted(syncFromRoute)
watch(() => route.name, syncFromRoute)
</script>

<style scoped>
.user-management-container {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.user-management-tabs {
  margin-bottom: 4px;
}

.user-management-tabs :deep(.el-tabs__nav-wrap)::after {
  background: var(--va-hairline);
}

.user-management-tabs :deep(.el-tabs__item) {
  font-size: 14px;
  font-weight: 500;
  color: var(--va-muted);
}

.user-management-tabs :deep(.el-tabs__item.is-active) {
  color: var(--va-ink);
  font-weight: 600;
}

.user-management-tabs :deep(.el-tabs__active-bar) {
  background-color: var(--va-accent);
}

.user-management-body {
  background: var(--va-paper);
}
</style>
