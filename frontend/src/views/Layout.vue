<template>
  <el-container class="layout-container">
    <!-- 侧边栏 -->
    <el-aside width="240px" class="sidebar">
      <div class="sidebar-header">
        <div class="logo">
          <AudioLines :size="28" class="logo-icon" />
          <span class="logo-text">语音质检助手</span>
        </div>
      </div>

      <el-menu
        :default-active="activeMenu"
        router
        class="sidebar-menu"
        background-color="transparent"
        text-color="#9c948a"
        active-text-color="#faf8f4"
        :unique-opened="true"
      >
        <el-menu-item index="/home">
          <el-icon><LayoutDashboard /></el-icon>
          <template #title>数据概览</template>
        </el-menu-item>
        <el-menu-item index="/rules">
          <el-icon><ListChecks /></el-icon>
          <template #title>规则管理</template>
        </el-menu-item>
        <el-menu-item index="/recordings">
          <el-icon><Mic /></el-icon>
          <template #title>录音管理</template>
        </el-menu-item>
        <el-menu-item index="/export">
          <el-icon><FileDown /></el-icon>
          <template #title>导出报告</template>
        </el-menu-item>
        <el-menu-item v-if="isAdmin" index="/storage">
          <el-icon><Trash2 /></el-icon>
          <template #title>存储清理</template>
        </el-menu-item>
        <el-menu-item v-if="isAdmin" index="/user-stats">
          <el-icon><Users /></el-icon>
          <template #title>用户统计</template>
        </el-menu-item>
        <el-menu-item v-if="isAdmin" index="/system-settings">
          <el-icon><Settings /></el-icon>
          <template #title>系统设置</template>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <!-- 主内容区 -->
    <el-container class="main-container">
      <el-header class="header">
        <div class="header-left">
          <h3 class="page-title">{{ pageTitle }}</h3>
        </div>
        <div class="header-right">
          <span class="user-info">{{ userInfo?.姓名 }} ({{ userInfo?.工号 }})</span>
          <el-button size="small" plain @click="handleLogout">
            <el-icon><LogOut /></el-icon>
            退出
          </el-button>
        </div>
      </el-header>

      <el-main class="main-content">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { AudioLines, LayoutDashboard, ListChecks, Mic, FileDown, Trash2, Users, Settings, LogOut } from 'lucide-vue-next'
import { now, formatDate } from '@/utils/timezone'
import api from '@/api'

const route = useRoute()
const router = useRouter()
const currentTime = ref('')

const activeMenu = computed(() => route.path)

const userInfo = computed(() => api.auth.getUserInfo())

const isAdmin = computed(() => userInfo.value?.loginid === 'admin')

const pageTitles = {
  '/home': '数据概览',
  '/rules': '规则管理',
  '/recordings': '录音管理',
  '/export': '导出报告',
  '/storage': '存储清理',
  '/user-stats': '用户统计',
  '/system-settings': '系统设置'
}

const pageTitle = computed(() => {
  if (route.path.startsWith('/recordings/')) return '录音详情'
  return pageTitles[route.path] || '语音质检助手'
})

function handleLogout() {
  api.auth.logout()
  router.push('/login')
}

function updateTime() {
  currentTime.value = now().format('YYYY-MM-DD HH:mm:ss')
}

let timeInterval = null

onMounted(() => {
  updateTime()
  timeInterval = setInterval(updateTime, 1000)
})

onUnmounted(() => {
  if (timeInterval) {
    clearInterval(timeInterval)
  }
})
</script>

<style scoped>
.layout-container {
  height: 100vh;
  background: var(--va-paper);
}

/* 侧边栏：墨色 */
.sidebar {
  background: var(--va-ink);
  display: flex;
  flex-direction: column;
}

.sidebar-header {
  padding: 24px 20px 20px;
  border-bottom: 1px solid rgba(250, 248, 244, 0.08);
}

.logo {
  display: flex;
  align-items: center;
  gap: 12px;
}

.logo-icon {
  color: var(--va-accent);
  flex-shrink: 0;
}

.logo-text {
  font-family: var(--va-font-display);
  font-size: 19px;
  font-weight: 700;
  color: #faf8f4;
  letter-spacing: 0.04em;
}

.sidebar-menu {
  flex: 1;
  border-right: none;
  background: transparent;
  padding: 12px 0;
}

:deep(.el-menu-item) {
  height: 44px;
  line-height: 44px;
  margin: 2px 12px;
  border-radius: var(--va-radius-sm);
  font-size: 13.5px;
  transition: background var(--va-duration) var(--va-ease), color var(--va-duration) var(--va-ease);
}

:deep(.el-menu-item:hover) {
  background: rgba(250, 248, 244, 0.06) !important;
  color: #faf8f4 !important;
}

:deep(.el-menu-item.is-active) {
  background: rgba(176, 68, 44, 0.16) !important;
  color: #faf8f4 !important;
}

:deep(.el-menu-item.is-active .el-icon) {
  color: var(--va-accent);
}

:deep(.el-menu-item.is-active::before) {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 20px;
  background: var(--va-accent);
  border-radius: 0 2px 2px 0;
}

/* 主内容区 */
.main-container {
  display: flex;
  flex-direction: column;
}

.header {
  background: var(--va-paper);
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 28px;
  border-bottom: 1px solid var(--va-hairline);
  z-index: 100;
}

.page-title {
  margin: 0;
  font-family: var(--va-font-display);
  font-size: 20px;
  font-weight: 700;
  color: var(--va-ink);
  letter-spacing: 0.02em;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.user-info {
  font-size: 13px;
  color: var(--va-muted);
  font-variant-numeric: tabular-nums;
}

.main-content {
  padding: 28px;
  overflow-y: auto;
  background: var(--va-paper);
}
</style>