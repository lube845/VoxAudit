<template>
  <div class="change-pwd-container">
    <div class="change-pwd-box">
      <div class="brand">
        <AudioLines :size="26" class="brand-icon" />
        <h1 class="title">智能语音质检系统</h1>
        <p class="subtitle">为了账号安全，请先修改密码再继续</p>
      </div>

      <el-alert
        :title="alertTitle"
        type="warning"
        :closable="false"
        show-icon
        style="margin-bottom: 20px"
      />

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="92px"
        @submit.prevent
      >
        <el-form-item label="工号">
          <el-input
            :model-value="loginid"
            disabled
            placeholder="-"
            size="large"
          />
        </el-form-item>
        <el-form-item label="旧密码" prop="old_password">
          <el-input
            v-model="form.old_password"
            type="password"
            placeholder="请输入当前密码"
            show-password
            autocomplete="current-password"
            size="large"
          />
        </el-form-item>
        <el-form-item label="新密码" prop="new_password">
          <el-input
            v-model="form.new_password"
            type="password"
            placeholder="请输入新密码（至少 6 位）"
            show-password
            autocomplete="new-password"
            size="large"
          />
        </el-form-item>
        <el-form-item label="确认新密码" prop="confirm_password">
          <el-input
            v-model="form.confirm_password"
            type="password"
            placeholder="请再次输入新密码"
            show-password
            autocomplete="new-password"
            size="large"
            @keyup.enter="handleSubmit"
          />
        </el-form-item>
        <el-form-item>
          <div class="button-group">
            <el-button
              type="primary"
              size="large"
              :loading="loading"
              @click="handleSubmit"
            >
              确认修改
            </el-button>
            <el-button
              size="large"
              @click="handleBackToLogin"
            >
              返回登录
            </el-button>
          </div>
        </el-form-item>
      </el-form>
    </div>
    <div class="footer-note">VoxAudit · 自动化通话质检</div>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { AudioLines } from 'lucide-vue-next'
import api from '@/api'

const router = useRouter()
const route = useRoute()
const formRef = ref(null)
const loading = ref(false)

// 从 localStorage 拿当前工号（只读展示）
const loginid = (() => {
  try { return JSON.parse(localStorage.getItem('user_info') || '{}').loginid || '' } catch { return '' }
})()

const form = reactive({
  old_password: '',
  new_password: '',
  confirm_password: ''
})

// 根据 localStorage 里的 expire_at 决定提示文案
const userInfo = (() => {
  try { return JSON.parse(localStorage.getItem('user_info') || '{}') } catch { return {} }
})()
const alertTitle = computed(() => {
  const exp = userInfo.password_expire_at
  if (exp === null || exp === undefined) return '首次登录 / 仍在使用默认密码，请修改'
  return '密码已超过 3 个月有效期，请修改'
})

const rules = {
  old_password: [
    { required: true, message: '请输入旧密码', trigger: 'blur' }
  ],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '新密码至少 6 位', trigger: 'blur' },
    {
      validator: (rule, value, cb) => {
        if (value && value === form.old_password) {
          return cb(new Error('新密码不能与旧密码相同'))
        }
        cb()
      },
      trigger: 'blur'
    }
  ],
  confirm_password: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    {
      validator: (rule, value, cb) => {
        if (value !== form.new_password) {
          return cb(new Error('两次输入的新密码不一致'))
        }
        cb()
      },
      trigger: 'blur'
    }
  ]
}

const handleSubmit = async () => {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    const res = await api.auth.changePassword({
      old_password: form.old_password,
      new_password: form.new_password
    })
    if (!res.success) {
      ElMessage.error(res.message || '密码修改失败')
      return
    }

    // 把后端返回的新过期时间写回 localStorage
    const stored = JSON.parse(localStorage.getItem('user_info') || '{}')
    stored.password_expire_at = res.password_expire_at
    localStorage.setItem('user_info', JSON.stringify(stored))

    ElMessage.success('密码已修改')

    // 跳到原来想去的页面；k 用户的默认页是催记管理
    const redirect = route.query.redirect
    const fallback = (stored.loginid || '').startsWith('k') && stored.loginid !== 'admin'
      ? '/collection-notes'
      : '/home'
    router.push(redirect || fallback)
  } catch (error) {
    ElMessage.error(error.message || '密码修改失败')
  } finally {
    loading.value = false
  }
}

// 兜底退出：清掉 localStorage 让路由守卫放行，跳回登录页
const handleBackToLogin = () => {
  api.auth.logout()
  router.push('/login')
}
</script>

<style scoped>
.change-pwd-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: var(--va-paper);
  background-image:
    linear-gradient(var(--va-hairline) 1px, transparent 1px),
    linear-gradient(90deg, var(--va-hairline) 1px, transparent 1px);
  background-size: 56px 56px;
  background-position: center;
  position: relative;
}

.change-pwd-container::before {
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(ellipse 70% 60% at 50% 45%, var(--va-paper) 30%, transparent 75%);
  pointer-events: none;
}

.change-pwd-box {
  position: relative;
  width: 460px;
  padding: 44px 44px 36px;
  background: #fff;
  border: 1px solid var(--va-hairline);
  border-radius: var(--va-radius-md);
  box-shadow: 0 2px 6px rgba(33, 29, 24, 0.05), 0 16px 48px rgba(33, 29, 24, 0.07);
}

.change-pwd-box::before {
  content: '';
  position: absolute;
  top: -1px;
  left: 32px;
  right: 32px;
  height: 2px;
  background: var(--va-accent);
}

.brand {
  text-align: center;
  margin-bottom: 24px;
}

.brand-icon {
  color: var(--va-accent);
}

.title {
  margin: 14px 0 8px;
  font-family: var(--va-font-display);
  font-size: 24px;
  font-weight: 700;
  color: var(--va-ink);
  letter-spacing: 0.05em;
}

.subtitle {
  margin: 0;
  font-size: 12.5px;
  color: var(--va-muted);
  letter-spacing: 0.12em;
}

.button-group {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 10px;
  width: 100%;
}

.button-group .el-button {
  width: 100%;
  margin-left: 0 !important;
  margin-right: 0 !important;
  font-weight: 600;
  letter-spacing: 0.25em;
}

.footer-note {
  position: relative;
  margin-top: 28px;
  font-size: 12px;
  color: var(--va-muted);
  letter-spacing: 0.2em;
}
</style>
