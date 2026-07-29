<template>
  <el-container class="layout-container">
    <!-- 侧边栏 -->
    <el-aside width="240px" class="sidebar">
      <div class="sidebar-header">
        <div class="logo">
          <span class="logo-icon">🎯</span>
          <span class="logo-text">语音质检助手</span>
        </div>
      </div>

      <el-menu
        :default-active="activeMenu"
        router
        class="sidebar-menu"
        background-color="#1a1a2e"
        text-color="#a0a0a0"
        active-text-color="#ffffff"
        :unique-opened="true"
      >
        <el-menu-item index="/home">
          <el-icon><HomeFilled /></el-icon>
          <template #title>数据概览</template>
        </el-menu-item>
        <el-menu-item index="/rules">
          <el-icon><Setting /></el-icon>
          <template #title>规则管理</template>
        </el-menu-item>
        <el-menu-item index="/recordings">
          <el-icon><Microphone /></el-icon>
          <template #title>录音管理</template>
        </el-menu-item>
        <el-menu-item index="/export">
          <el-icon><Download /></el-icon>
          <template #title>导出报告</template>
        </el-menu-item>
        <el-menu-item v-if="isAdmin" index="/storage">
          <el-icon><Delete /></el-icon>
          <template #title>存储清理</template>
        </el-menu-item>
        <el-menu-item v-if="isAdmin" index="/user-stats">
          <el-icon><User /></el-icon>
          <template #title>用户统计</template>
        </el-menu-item>
        <el-menu-item v-if="isAdmin" index="/system-settings">
          <el-icon><Tools /></el-icon>
          <template #title>系统设置</template>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <!-- 主内容区 -->
    <el-container class="main-container">
      <el-header class="header">
        <div class="header-left">
          <h3>评分规则管理</h3>
        </div>
        <div class="header-right">
          <span class="user-info">{{ userInfo?.姓名 }} ({{ userInfo?.工号 }})</span>
          <el-button type="danger" size="small" @click="handleLogout">退出</el-button>
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
import { Setting, Microphone, HomeFilled, Download, Delete, User, Tools } from '@element-plus/icons-vue'
import { now, formatDate } from '@/utils/timezone'
import api from '@/api'

const route = useRoute()
const router = useRouter()
const currentTime = ref('')

const activeMenu = computed(() => route.path)

const userInfo = computed(() => api.auth.getUserInfo())

const isAdmin = computed(() => userInfo.value?.loginid === 'admin')

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
  background: #f5f7fa;
}

/* 侧边栏 */
.sidebar {
  background: #1a1a2e;
  display: flex;
  flex-direction: column;
  box-shadow: 2px 0 10px rgba(0, 0, 0, 0.1);
}

.sidebar-header {
  padding: 20px;
  border-bottom: 1px solid #2a2a4e;
}

.logo {
  display: flex;
  align-items: center;
  gap: 10px;
}

.logo-icon {
  font-size: 28px;
}

.logo-text {
  font-size: 20px;
  font-weight: 700;
  color: #ffffff;
}

.sidebar-menu {
  flex: 1;
  border-right: none;
  background: transparent;
}

:deep(.el-menu-item) {
  height: 50px;
  line-height: 50px;
  margin: 4px 12px;
  border-radius: 8px;
}

:deep(.el-menu-item:hover) {
  background: #2a2a4e !important;
}

:deep(.el-menu-item.is-active) {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
  color: #ffffff !important;
}

:deep(.el-menu-item.is-active::before) {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 4px;
  height: 24px;
  background: #ffffff;
  border-radius: 0 4px 4px 0;
}

/* 主内容区 */
.main-container {
  display: flex;
  flex-direction: column;
}

.header {
  background: #ffffff;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 24px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
  z-index: 100;
}

.header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

.time {
  font-size: 13px;
  color: #909399;
}

.user-info {
  margin-right: 16px;
  font-size: 13px;
  color: #606266;
}

.main-content {
  padding: 24px;
  overflow-y: auto;
  background: #f5f7fa;
}
</style>