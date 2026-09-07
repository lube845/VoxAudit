<template>
  <div class="k-user-management-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>客服账号管理</span>
          <el-button type="primary" size="small" :loading="loading" @click="loadList">
            <el-icon><RefreshCw /></el-icon>
            刷新
          </el-button>
        </div>
      </template>

      <div class="hint">
        客服账号首次以默认密码（<code>kefu123456</code>）登录后自动创建；
        在此可重置任意客服账号的密码为默认值，并强制其下次登录时修改密码。
      </div>

      <el-table :data="list" stripe border v-loading="loading" empty-text="暂无客服账号">
        <el-table-column type="index" label="#" width="60" />
        <el-table-column prop="loginid" label="工号" min-width="160" />
        <el-table-column label="强制改密标志" width="130">
          <template #default="{ row }">
            <el-tag v-if="row.must_change" type="warning" size="small">是</el-tag>
            <el-tag v-else type="info" size="small" effect="plain">否</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="下次登录需改密" width="150">
          <template #default="{ row }">
            <el-tag v-if="row.needs_change" type="danger" size="small">需改密</el-tag>
            <el-tag v-else type="success" size="small" effect="plain">正常</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="最后改密时间" min-width="200">
          <template #default="{ row }">
            <span v-if="row.password_changed_at">{{ formatDateTime(row.password_changed_at) }}</span>
            <span v-else class="muted">从未改密</span>
          </template>
        </el-table-column>
        <el-table-column label="密码过期时间" min-width="200">
          <template #default="{ row }">
            <span v-if="row.password_expire_at">{{ formatTimestamp(row.password_expire_at) }}</span>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" min-width="200">
          <template #default="{ row }">
            <span v-if="row.created_at" class="muted">{{ formatDateTime(row.created_at) }}</span>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button
              type="danger"
              size="small"
              link
              @click="confirmReset(row)"
            >
              重置密码
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { RefreshCw } from 'lucide-vue-next'
import api from '@/api'

const loading = ref(false)
const list = ref([])

function formatDateTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (isNaN(d.getTime())) return iso
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function formatTimestamp(ts) {
  if (!ts) return ''
  return formatDateTime(new Date(ts * 1000).toISOString())
}

async function loadList() {
  loading.value = true
  try {
    const res = await api.kUserAdmin.list()
    list.value = res.items || []
  } finally {
    loading.value = false
  }
}

async function confirmReset(row) {
  try {
    await ElMessageBox.confirm(
      `确认将 ${row.loginid} 的密码重置为默认密码（kefu123456）？该账号下次登录将被强制改密。`,
      '重置密码',
      {
        type: 'warning',
        confirmButtonText: '确认重置',
        cancelButtonText: '取消',
      }
    )
  } catch {
    return
  }

  loading.value = true
  try {
    const res = await api.kUserAdmin.resetPassword(row.loginid)
    ElMessage.success(res.message || '已重置')
    await loadList()
  } finally {
    loading.value = false
  }
}

onMounted(loadList)
</script>

<style scoped>
.k-user-management-container {
  max-width: 1200px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
  color: var(--va-ink);
}

.hint {
  font-size: 13px;
  color: var(--va-muted);
  margin-bottom: 16px;
  padding: 10px 14px;
  background: rgba(176, 125, 42, 0.08);
  border-left: 3px solid var(--va-accent);
  border-radius: var(--va-radius-sm);
}

.hint code {
  font-family: var(--va-font-mono, monospace);
  background: rgba(0, 0, 0, 0.05);
  padding: 1px 6px;
  border-radius: 3px;
  color: var(--va-ink);
}

.muted {
  color: var(--va-muted);
}
</style>
