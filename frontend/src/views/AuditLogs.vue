<template>
  <div class="audit-logs-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>审计日志</span>
          <div class="header-actions">
            <el-button type="primary" size="small" :loading="loading" @click="loadList">
              <el-icon><RefreshCw /></el-icon> 刷新
            </el-button>
            <el-button type="primary" size="small" @click="handleExport" :loading="exporting">
              <el-icon><Download /></el-icon> 导出 CSV
            </el-button>
          </div>
        </div>
      </template>

      <div class="hint">
        仅 <b>管理员</b> 可见。审计每个人的操作行为，默认隐藏 <code>page.view</code> 类页面访问（勾选下方开关以显示）。
        同一用户对同一目标同一操作在 <b>5 分钟</b> 内只记一次（去重）。
      </div>

      <!-- 筛选 -->
      <el-form :inline="true" class="filter-form">
        <el-form-item label="操作人">
          <el-select v-model="filters.actor_loginid" placeholder="全部" clearable filterable style="width: 180px">
            <el-option v-for="a in actorOptions" :key="a.loginid"
              :label="`${a.name || a.loginid} (${a.loginid})`" :value="a.loginid" />
          </el-select>
        </el-form-item>
        <el-form-item label="操作类型">
          <el-select v-model="filters.action" placeholder="全部" clearable filterable style="width: 220px">
            <el-option v-for="a in actionOptions" :key="a.action"
              :label="`${a.action} (${a.count})`" :value="a.action" />
          </el-select>
        </el-form-item>
        <el-form-item label="目标类型">
          <el-input v-model="filters.target_type" placeholder="如 rule/recording" clearable style="width: 180px" />
        </el-form-item>
        <el-form-item label="时间范围">
          <el-date-picker v-model="filters.timeRange" type="datetimerange"
            range-separator="至" start-placeholder="开始" end-placeholder="结束"
            format="YYYY-MM-DD HH:mm:ss" value-format="YYYY-MM-DDTHH:mm:ss"
            style="width: 360px" />
        </el-form-item>
        <el-form-item label="关键词">
          <el-input v-model="filters.keyword" placeholder="操作人姓名 / 目标描述" clearable style="width: 200px" />
        </el-form-item>
        <el-form-item label="只看写操作">
          <el-switch v-model="filters.writeOnly" />
        </el-form-item>
        <el-form-item class="filter-actions">
          <el-button @click="handleReset">重置</el-button>
          <el-button type="primary" @click="handleQuery">查询</el-button>
        </el-form-item>
      </el-form>

      <el-table :data="list" stripe border v-loading="loading" empty-text="暂无审计记录">
        <el-table-column prop="created_at" label="时间" min-width="170" :formatter="formatTime" />
        <el-table-column label="操作人" min-width="160">
          <template #default="{ row }">
            <span>{{ row.actor_name || row.actor_loginid }}</span>
            <el-tag size="small" :type="roleTagType(row.actor_role)" effect="plain" style="margin-left: 6px">
              {{ roleLabel(row.actor_role) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="action" label="操作类型" min-width="200" />
        <el-table-column label="目标" min-width="240" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.target_type" class="target-type">{{ row.target_type }}</span>
            <span v-if="row.target_id" class="target-id">#{{ row.target_id }}</span>
            <span v-if="row.target_label" class="target-label">{{ row.target_label }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="ip" label="IP" min-width="120" />
        <el-table-column label="结果" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.result === 'success'" type="success" size="small" effect="plain">成功</el-tag>
            <el-tag v-else type="danger" size="small">失败</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" size="small" link @click="openDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :page-sizes="[20, 50, 100, 200]"
          :total="total"
          layout="total, sizes, prev, pager, next, jumper"
          background
        />
      </div>
    </el-card>

    <!-- 详情抽屉 -->
    <el-drawer v-model="detailVisible" title="审计日志详情" size="640px" destroy-on-close>
      <div v-if="currentRow" class="detail-content">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="时间">{{ formatTime(currentRow) }}</el-descriptions-item>
          <el-descriptions-item label="操作人">
            {{ currentRow.actor_name || currentRow.actor_loginid }}（{{ currentRow.actor_loginid }}）
          </el-descriptions-item>
          <el-descriptions-item label="角色">{{ roleLabel(currentRow.actor_role) }}</el-descriptions-item>
          <el-descriptions-item label="操作类型"><code>{{ currentRow.action }}</code></el-descriptions-item>
          <el-descriptions-item label="目标类型">{{ currentRow.target_type || '—' }}</el-descriptions-item>
          <el-descriptions-item label="目标 ID">{{ currentRow.target_id || '—' }}</el-descriptions-item>
          <el-descriptions-item label="目标描述">{{ currentRow.target_label || '—' }}</el-descriptions-item>
          <el-descriptions-item label="IP">{{ currentRow.ip || '—' }}</el-descriptions-item>
          <el-descriptions-item label="User-Agent">{{ currentRow.user_agent || '—' }}</el-descriptions-item>
          <el-descriptions-item label="结果">{{ currentRow.result }}</el-descriptions-item>
        </el-descriptions>

        <h4>业务上下文（detail）</h4>
        <pre class="detail-json">{{ formatDetail(currentRow.detail) }}</pre>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { RefreshCw, Download } from 'lucide-vue-next'
import api from '@/api'

const loading = ref(false)
const exporting = ref(false)
const list = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

const actorOptions = ref([])
const actionOptions = ref([])

const filters = reactive({
  actor_loginid: '',
  action: '',
  target_type: '',
  keyword: '',
  timeRange: null,
  writeOnly: true,  // 默认只看写操作
})

const detailVisible = ref(false)
const currentRow = ref(null)

// ——— 工具 ———
function formatTime(row, col, cell) {
  const val = typeof row === 'object' ? row?.created_at : row
  if (!val) return ''
  const d = new Date(val)
  if (isNaN(d.getTime())) return String(val)
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}

function formatDetail(detail) {
  if (!detail) return '（空）'
  try {
    return JSON.stringify(detail, null, 2)
  } catch {
    return String(detail)
  }
}

function roleLabel(role) {
  return { admin: '管理员', k_user: '客服', oa_user: 'OA' }[role] || (role || '未知')
}
function roleTagType(role) {
  return { admin: 'danger', k_user: 'warning', oa_user: 'info' }[role] || 'info'
}

function buildParams() {
  return {
    actor_loginid: filters.actor_loginid || undefined,
    action: filters.action || undefined,
    target_type: filters.target_type || undefined,
    keyword: filters.keyword || undefined,
    start_time: filters.timeRange?.[0] || undefined,
    end_time: filters.timeRange?.[1] || undefined,
    include_page_view: !filters.writeOnly,
    page: page.value,
    page_size: pageSize.value,
  }
}

async function loadList() {
  loading.value = true
  try {
    const res = await api.auditLog.list(buildParams())
    list.value = res.items || []
    total.value = res.total || 0
  } finally {
    loading.value = false
  }
}

async function loadOptions() {
  try {
    const [a, ac] = await Promise.all([
      api.auditLog.actors(),
      api.auditLog.actions(),
    ])
    actorOptions.value = a.items || []
    actionOptions.value = ac.items || []
  } catch {
    /* 忽略选项失败，不影响列表 */
  }
}

function handleQuery() { page.value = 1; loadList() }

function handleReset() {
  filters.actor_loginid = ''
  filters.action = ''
  filters.target_type = ''
  filters.keyword = ''
  filters.timeRange = null
  filters.writeOnly = true
  page.value = 1
  loadList()
}

function openDetail(row) {
  currentRow.value = row
  detailVisible.value = true
}

async function handleExport() {
  exporting.value = true
  try {
    const params = { ...buildParams() }
    delete params.page
    delete params.page_size
    const blob = await api.auditLog.export(params)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `audit_logs_${new Date().toISOString().slice(0, 19).replace(/[T:]/g, '')}.csv`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    ElMessage.success('导出已开始')
  } catch {
    /* 拦截器已提示 */
  } finally {
    exporting.value = false
  }
}

watch([page, pageSize], loadList)
onMounted(() => { loadOptions(); loadList() })
</script>

<style scoped>
.audit-logs-container { max-width: 1400px; }
.card-header {
  display: flex; align-items: center; justify-content: space-between;
  font-weight: 600; color: var(--va-ink);
}
.header-actions { display: flex; gap: 8px; }
.hint {
  font-size: 13px; color: var(--va-muted);
  margin-bottom: 16px; padding: 10px 14px;
  background: rgba(176, 125, 42, 0.08);
  border-left: 3px solid var(--va-accent);
  border-radius: var(--va-radius-sm);
}
.hint code, .target-type {
  font-family: var(--va-font-mono, monospace);
  background: rgba(0, 0, 0, 0.05);
  padding: 1px 6px; border-radius: 3px;
  color: var(--va-ink); font-size: 12px;
}
.filter-form { display: flex; flex-wrap: wrap; align-items: center; row-gap: 4px; margin-bottom: 14px; }
.filter-form :deep(.el-form-item) { margin-right: 14px; margin-bottom: 8px; }
.filter-form :deep(.el-form-item__label) { color: var(--va-ink-soft); font-size: 13px; }
.filter-actions { margin-left: auto; margin-right: 0; }
.target-type { margin-right: 6px; }
.target-id { color: var(--va-muted); margin-right: 6px; }
.target-label { color: var(--va-ink-soft); }
.pagination { margin-top: 16px; display: flex; justify-content: flex-end; }
.detail-content h4 { margin: 18px 0 8px; font-size: 13px; color: var(--va-ink-soft); }
.detail-json {
  font-family: var(--va-font-mono, monospace);
  background: var(--va-paper-deep);
  border: 1px solid var(--va-hairline);
  border-radius: var(--va-radius-sm);
  padding: 12px;
  font-size: 12.5px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 480px;
  overflow-y: auto;
}
</style>