<template>
  <div class="k-user-management-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>客服账号管理</span>
          <div class="header-actions">
            <el-button type="primary" size="small" @click="openCreateDialog">
              <el-icon><UserPlus /></el-icon>
              添加白名单
            </el-button>
            <el-button type="primary" size="small" :loading="loading" @click="loadList">
              <el-icon><RefreshCw /></el-icon>
              刷新
            </el-button>
          </div>
        </div>
      </template>

      <div class="hint">
        客服账号必须由管理员添加白名单后才能登录，默认密码 <code>kefu123456</code>，首次登录强制改密；
        在此可重置任意客服账号的密码为默认值，并强制其下次登录时修改密码。
      </div>

      <el-table :data="list" stripe border v-loading="loading" empty-text="暂无客服账号">
        <el-table-column type="index" label="#" width="60" />
        <el-table-column prop="loginid" label="工号" min-width="140" />
        <el-table-column label="姓名" min-width="120">
          <template #default="{ row }">
            <span v-if="row.name">{{ row.name }}</span>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="部门" min-width="120">
          <template #default="{ row }">
            <span v-if="row.department">{{ row.department }}</span>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
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
        <el-table-column label="操作" width="320" fixed="right">
          <template #default="{ row }">
            <el-button
              type="primary"
              size="small"
              link
              @click="openEditDialog(row)"
            >
              修改
            </el-button>
            <el-button
              type="warning"
              size="small"
              link
              @click="confirmClearData(row)"
            >
              清除数据
            </el-button>
            <el-button
              type="danger"
              size="small"
              link
              @click="confirmReset(row)"
            >
              重置密码
            </el-button>
            <el-button
              type="danger"
              size="small"
              link
              @click="confirmRemove(row)"
            >
              剔除白名单
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 修改客服信息弹窗 -->
    <el-dialog
      v-model="editDialogVisible"
      title="修改客服信息"
      width="420px"
      :close-on-click-modal="false"
      @closed="resetEditForm"
    >
      <el-form
        ref="editFormRef"
        :model="editForm"
        :rules="editFormRules"
        label-width="72px"
        @submit.prevent
      >
        <el-form-item label="工号">
          <el-input :model-value="editForm.loginid" disabled />
        </el-form-item>
        <el-form-item label="姓名" prop="name">
          <el-input
            v-model="editForm.name"
            placeholder="客服姓名"
            maxlength="64"
            clearable
          />
        </el-form-item>
        <el-form-item label="部门" prop="department">
          <el-input
            v-model="editForm.department"
            placeholder="所属部门"
            maxlength="64"
            clearable
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="editSubmitting" @click="submitEdit">
          保存
        </el-button>
      </template>
    </el-dialog>

    <!-- 添加白名单弹窗 -->
    <el-dialog
      v-model="createDialogVisible"
      title="添加客服白名单"
      width="420px"
      :close-on-click-modal="false"
      @closed="resetCreateForm"
    >
      <el-form
        ref="createFormRef"
        :model="createForm"
        :rules="createFormRules"
        label-width="72px"
        @submit.prevent
      >
        <el-form-item label="工号" prop="loginid">
          <el-input
            v-model="createForm.loginid"
            placeholder="k 开头，例如 k0002"
            maxlength="50"
            clearable
          />
        </el-form-item>
        <el-form-item label="姓名" prop="name">
          <el-input
            v-model="createForm.name"
            placeholder="客服姓名（可选）"
            maxlength="64"
            clearable
          />
        </el-form-item>
        <el-form-item label="部门" prop="department">
          <el-input
            v-model="createForm.department"
            placeholder="所属部门（可选）"
            maxlength="64"
            clearable
          />
        </el-form-item>
      </el-form>
      <div class="dialog-hint">
        添加后默认密码为 <code>kefu123456</code>，首次登录强制改密。
      </div>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="createSubmitting" @click="submitCreate">
          添加
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { RefreshCw, UserPlus } from 'lucide-vue-next'
import api from '@/api'

const clearingData = ref(false)
const removingUser = ref(false)

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

async function confirmClearData(row) {
  // 高危操作：要求输入工号作为最终确认，避免误点
  let typed
  try {
    ({ value: typed } = await ElMessageBox.prompt(
      `确认清除 ${row.loginid} 的全部业务数据？\n` +
        '将删除该账号的所有录音、转写、评分结果、评分规则，以及 MinIO 上的录音文件。\n' +
        '此操作不可撤销。账号本身和密码保持不变。\n\n' +
        `请输入工号 ${row.loginid} 以继续：`,
      '清除数据',
      {
        type: 'warning',
        inputPlaceholder: `输入 ${row.loginid}`,
        inputValidator: (v) => (v && v.trim() === row.loginid ? true : '工号不匹配'),
        inputErrorMessage: '工号不匹配',
        confirmButtonText: '确认清除',
        cancelButtonText: '取消',
      }
    ))
  } catch {
    return
  }
  if (!typed || typed.trim() !== row.loginid) return

  clearingData.value = true
  try {
    const res = await api.kUserAdmin.clearData(row.loginid)
    ElMessage.success(res.message || '已清除数据')
    await loadList()
  } catch (e) {
    // 拦截器已提示
  } finally {
    clearingData.value = false
  }
}

async function confirmRemove(row) {
  // 最高危操作：清除全部数据 + 剔除白名单（账号将无法再登录，除非再次被 admin 添加）
  let typed
  try {
    ({ value: typed } = await ElMessageBox.prompt(
      `⚠️ 即将从白名单中剔除 ${row.loginid}。\n` +
        '此操作将：\n' +
        '  · 删除该账号的全部录音、转写、评分结果、评分规则\n' +
        '  · 删除 MinIO 上的录音文件\n' +
        '  · 删除白名单条目（账号将无法再登录，除非再次添加）\n\n' +
        '此操作不可撤销。\n\n' +
        `请输入工号 ${row.loginid} 以继续：`,
      '剔除白名单',
      {
        type: 'error',
        inputPlaceholder: `输入 ${row.loginid}`,
        inputValidator: (v) => (v && v.trim() === row.loginid ? true : '工号不匹配'),
        inputErrorMessage: '工号不匹配',
        confirmButtonText: '确认剔除',
        cancelButtonText: '取消',
      }
    ))
  } catch {
    return
  }
  if (!typed || typed.trim() !== row.loginid) return

  removingUser.value = true
  try {
    const res = await api.kUserAdmin.remove(row.loginid)
    ElMessage.success(res.message || '已剔除白名单')
    await loadList()
  } catch (e) {
    // 拦截器已提示
  } finally {
    removingUser.value = false
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

// —— 添加白名单 ——
const createDialogVisible = ref(false)
const createSubmitting = ref(false)
const createFormRef = ref(null)
const createForm = reactive({ loginid: '', name: '', department: '' })

const createFormRules = {
  loginid: [
    { required: true, message: '请输入工号', trigger: 'blur' },
    {
      validator: (_, value, cb) => {
        if (!value || !value.trim().startsWith('k')) {
          return cb(new Error('工号必须以 k 开头'))
        }
        cb()
      },
      trigger: 'blur',
    },
  ],
}

function openCreateDialog() {
  createDialogVisible.value = true
}

function resetCreateForm() {
  createForm.loginid = ''
  createForm.name = ''
  createForm.department = ''
  createFormRef.value?.clearValidate?.()
}

async function submitCreate() {
  const valid = await createFormRef.value?.validate().catch(() => false)
  if (!valid) return

  createSubmitting.value = true
  try {
    const res = await api.kUserAdmin.create({
      loginid: createForm.loginid.trim(),
      name: createForm.name.trim(),
      department: createForm.department.trim(),
    })
    ElMessage.success(res.message || '已添加')
    createDialogVisible.value = false
    await loadList()
  } catch (e) {
    // 拦截器已经提示过错误信息
  } finally {
    createSubmitting.value = false
  }
}

// —— 修改客服信息 ——
const editDialogVisible = ref(false)
const editSubmitting = ref(false)
const editFormRef = ref(null)
const editForm = reactive({ loginid: '', name: '', department: '' })

const editFormRules = {
  name: [{ max: 64, message: '姓名长度不能超过 64', trigger: 'blur' }],
  department: [{ max: 64, message: '部门长度不能超过 64', trigger: 'blur' }],
}

function openEditDialog(row) {
  editForm.loginid = row.loginid || ''
  editForm.name = row.name || ''
  editForm.department = row.department || ''
  editDialogVisible.value = true
}

function resetEditForm() {
  editForm.loginid = ''
  editForm.name = ''
  editForm.department = ''
  editFormRef.value?.clearValidate?.()
}

async function submitEdit() {
  const valid = await editFormRef.value?.validate().catch(() => false)
  if (!valid) return

  editSubmitting.value = true
  try {
    const res = await api.kUserAdmin.update(editForm.loginid, {
      name: editForm.name.trim(),
      department: editForm.department.trim(),
    })
    ElMessage.success(res.message || '已保存')
    editDialogVisible.value = false
    await loadList()
  } catch (e) {
    // 拦截器已经提示过错误信息
  } finally {
    editSubmitting.value = false
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

.header-actions {
  display: flex;
  gap: 8px;
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

.hint code,
.dialog-hint code {
  font-family: var(--va-font-mono, monospace);
  background: rgba(0, 0, 0, 0.05);
  padding: 1px 6px;
  border-radius: 3px;
  color: var(--va-ink);
}

.dialog-hint {
  font-size: 12px;
  color: var(--va-muted);
  margin-top: -4px;
}

.muted {
  color: var(--va-muted);
}
</style>
