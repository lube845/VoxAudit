<template>
  <div class="storage-container">
    <el-card class="storage-card">
      <template #header>
        <div class="card-header">
          <span>存储概览</span>
          <el-button type="primary" link @click="refreshStorageInfo">
            <el-icon><Refresh /></el-icon> 刷新
          </el-button>
        </div>
      </template>

      <el-row :gutter="20" v-loading="loading">
        <el-col :span="6">
          <div class="stat-item">
            <div class="stat-label">总存储</div>
            <div class="stat-value">{{ formatSize(storageInfo.total_size) }}</div>
            <div class="stat-desc">{{ storageInfo.total_count }} 个对象</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-item">
            <div class="stat-label">录音存储</div>
            <div class="stat-value highlight">{{ formatSize(storageInfo.recordings_size) }}</div>
            <div class="stat-desc">{{ storageInfo.recordings_count }} 个录音</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-item">
            <div class="stat-label">其他存储</div>
            <div class="stat-value">{{ formatSize(storageInfo.other_size) }}</div>
            <div class="stat-desc">{{ storageInfo.other_count }} 个对象</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-item">
            <div class="stat-label">可用空间</div>
            <div class="stat-value normal">-</div>
            <div class="stat-desc">对象存储</div>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <el-tabs v-model="activeTab" class="storage-tabs">
      <!-- 录音清理 -->
      <el-tab-pane label="录音清理" name="recordings">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>录音文件清理</span>
            </div>
          </template>

          <el-form :inline="true" class="filter-form">
            <el-form-item label="按日期删除">
              <el-date-picker
                v-model="deleteBeforeDate"
                type="date"
                placeholder="删除此日期之前的录音"
                format="YYYY-MM-DD"
                value-format="YYYY-MM-DD"
                clearable
              />
            </el-form-item>
            <el-form-item>
              <el-button type="danger" @click="handleDeleteByDate" :loading="deleting">
                删除选中日期前的录音
              </el-button>
            </el-form-item>
          </el-form>

          <el-divider />

          <div class="list-header">
            <span>录音文件列表 ({{ objectList.length }} 个)</span>
            <el-button type="primary" link @click="loadObjects">
              <el-icon><Refresh /></el-icon> 刷新
            </el-button>
          </div>

          <el-table :data="objectList" stripe border v-loading="loadingObjects">
            <el-table-column prop="object_key" label="文件路径" min-width="200" />
            <el-table-column prop="size" label="大小" width="120" :formatter="formatSizeColumn" />
            <el-table-column prop="last_modified" label="修改时间" width="180" />
            <el-table-column label="操作" width="80" fixed="right">
              <template #default="{ row }">
                <el-button type="danger" size="small" link @click="handleDeleteSingle(row)">
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <!-- 缓存清理 -->
      <el-tab-pane label="缓存清理" name="cache">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>系统缓存</span>
              <el-button type="danger" @click="handleClearAllCache" :loading="clearingCache">
                清理所有缓存
              </el-button>
            </div>
          </template>

          <el-table :data="cacheList" stripe border v-loading="loadingCache">
            <el-table-column prop="cache_type" label="缓存类型" width="150" />
            <el-table-column prop="description" label="描述" width="200" />
            <el-table-column prop="count" label="文件数" width="100" />
            <el-table-column prop="size" label="大小" width="120" :formatter="formatSizeColumn" />
            <el-table-column label="操作" width="120" fixed="right">
              <template #default="{ row }">
                <el-button type="danger" size="small" @click="handleClearCache(row.cache_type)" :loading="clearingCache">
                  清理
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import api from '@/api'

const loading = ref(false)
const loadingObjects = ref(false)
const loadingCache = ref(false)
const deleting = ref(false)
const clearingCache = ref(false)
const activeTab = ref('recordings')

const storageInfo = ref({
  total_size: 0,
  total_count: 0,
  recordings_size: 0,
  recordings_count: 0,
  other_size: 0,
  other_count: 0,
})

const objectList = ref([])
const cacheList = ref([])
const deleteBeforeDate = ref('')

function formatSize(bytes) {
  if (!bytes || bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let i = 0
  while (bytes >= 1024 && i < units.length - 1) {
    bytes /= 1024
    i++
  }
  return `${bytes.toFixed(2)} ${units[i]}`
}

function formatSizeColumn(row, column, cellValue) {
  return formatSize(cellValue)
}

async function refreshStorageInfo() {
  loading.value = true
  try {
    const res = await api.storage.getInfo()
    storageInfo.value = res
  } catch (e) {
    console.error('获取存储信息失败', e)
  } finally {
    loading.value = false
  }
}

async function loadObjects() {
  loadingObjects.value = true
  try {
    const res = await api.storage.listObjects({ prefix: 'recordings/', limit: 500 })
    objectList.value = res.objects || []
  } catch (e) {
    console.error('获取对象列表失败', e)
  } finally {
    loadingObjects.value = false
  }
}

async function loadCacheInfo() {
  loadingCache.value = true
  try {
    const res = await api.storage.getCacheInfo()
    cacheList.value = res || []
  } catch (e) {
    console.error('获取缓存信息失败', e)
  } finally {
    loadingCache.value = false
  }
}

async function handleDeleteByDate() {
  if (!deleteBeforeDate.value) {
    ElMessage.warning('请选择日期')
    return
  }

  try {
    await ElMessageBox.confirm(
      `确定删除 ${deleteBeforeDate.value} 之前的所有录音吗？此操作不可恢复。`,
      '确认删除',
      { type: 'warning' }
    )

    deleting.value = true
    const res = await api.storage.delete({ before_date: deleteBeforeDate.value })
    ElMessage.success(res.message || '删除成功')
    deleteBeforeDate.value = ''
    await refreshStorageInfo()
    await loadObjects()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败')
    }
  } finally {
    deleting.value = false
  }
}

async function handleDeleteSingle(row) {
  try {
    await ElMessageBox.confirm(
      `确定删除文件 ${row.object_key} 吗？此操作不可恢复。`,
      '确认删除',
      { type: 'warning' }
    )

    deleting.value = true
    const res = await api.storage.delete({ object_keys: [row.object_key] })
    ElMessage.success(res.message || '删除成功')
    await refreshStorageInfo()
    await loadObjects()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败')
    }
  } finally {
    deleting.value = false
  }
}

async function handleClearCache(cacheType) {
  try {
    await ElMessageBox.confirm('确定清理此缓存吗？', '确认清理', { type: 'warning' })

    clearingCache.value = true
    const res = await api.storage.clearCache(cacheType)
    ElMessage.success(res.message || '清理成功')
    await loadCacheInfo()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('清理失败')
    }
  } finally {
    clearingCache.value = false
  }
}

async function handleClearAllCache() {
  try {
    await ElMessageBox.confirm('确定清理所有缓存吗？', '确认清理', { type: 'warning' })

    clearingCache.value = true
    const res = await api.storage.clearCache(null)
    ElMessage.success(res.message || '清理成功')
    await loadCacheInfo()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('清理失败')
    }
  } finally {
    clearingCache.value = false
  }
}

onMounted(() => {
  refreshStorageInfo()
  loadObjects()
  loadCacheInfo()
})
</script>

<style scoped>
.storage-container {
  max-width: 1400px;
}

.storage-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.stat-item {
  text-align: center;
  padding: 20px 10px;
  background: #f5f7fa;
  border-radius: 8px;
}

.stat-label {
  font-size: 14px;
  color: #909399;
  margin-bottom: 8px;
}

.stat-value {
  font-size: 24px;
  font-weight: 600;
  color: #303133;
}

.stat-value.highlight {
  color: #409eff;
}

.stat-value.normal {
  color: #67c23a;
}

.stat-desc {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

.storage-tabs {
  margin-top: 20px;
}

.filter-form {
  margin-bottom: 10px;
}

.list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
  font-size: 14px;
  color: #606266;
}
</style>