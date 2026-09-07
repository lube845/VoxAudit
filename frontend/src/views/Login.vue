<template>
  <div class="login-container">
    <div class="login-box">
      <div class="brand">
        <AudioLines :size="26" class="brand-icon" />
        <h1 class="title">智能语音质检系统</h1>
        <p class="subtitle">ASR 转写 · AI 评分 · 催收通话质检平台</p>
      </div>
      <el-form ref="formRef" :model="form" :rules="rules" class="login-form">
        <el-form-item prop="loginid">
          <el-input
            v-model="form.loginid"
            placeholder="工号"
            :prefix-icon="User"
            size="large"
          />
        </el-form-item>
        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            :type="showPassword ? 'text' : 'password'"
            placeholder="密码"
            :prefix-icon="Lock"
            size="large"
            @keyup.enter="handleLogin"
          >
            <template #suffix>
              <el-icon class="password-toggle" @click="showPassword = !showPassword">
                <component :is="showPassword ? Eye : EyeOff" />
              </el-icon>
            </template>
          </el-input>
        </el-form-item>
        <el-form-item>
          <el-button
            type="primary"
            size="large"
            :loading="loading"
            class="login-button"
            @click="handleLogin"
          >
            登录
          </el-button>
        </el-form-item>
      </el-form>
    </div>

    <!-- 强制改密弹窗：k 账号首次登录 / 密码过期时弹出，不让绕过 -->
    <el-dialog
      v-model="changePwdDialog.visible"
      :title="changePwdDialog.title"
      width="440px"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
      :show-close="false"
      align-center
    >
      <el-alert
        v-if="changePwdDialog.title"
        :title="changePwdDialog.title"
        type="warning"
        :closable="false"
        show-icon
        style="margin-bottom: 16px"
      />
      <el-form
        ref="changePwdFormRef"
        :model="changePwdDialog.form"
        :rules="changePwdDialog.rules"
        label-width="92px"
        @submit.prevent
      >
        <el-form-item label="旧密码" prop="old_password">
          <el-input
            v-model="changePwdDialog.form.old_password"
            type="password"
            placeholder="请输入当前密码"
            show-password
            autocomplete="current-password"
          />
        </el-form-item>
        <el-form-item label="新密码" prop="new_password">
          <el-input
            v-model="changePwdDialog.form.new_password"
            type="password"
            placeholder="请输入新密码（至少 6 位）"
            show-password
            autocomplete="new-password"
          />
        </el-form-item>
        <el-form-item label="确认新密码" prop="confirm_password">
          <el-input
            v-model="changePwdDialog.form.confirm_password"
            type="password"
            placeholder="请再次输入新密码"
            show-password
            autocomplete="new-password"
            @keyup.enter="submitChangePassword"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="handleBackToLoginFromDialog">返回登录</el-button>
        <el-button
          type="primary"
          :loading="changePwdDialog.loading"
          @click="submitChangePassword"
        >
          确认修改
        </el-button>
      </template>
    </el-dialog>

    <div class="footer-note">VoxAudit · 自动化通话质检</div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock, Eye, EyeOff, AudioLines } from 'lucide-vue-next'
import api from '@/api'

const router = useRouter()
const formRef = ref(null)
const loading = ref(false)
const showPassword = ref(false)

const form = reactive({
  loginid: '',
  password: ''
})

const rules = {
  loginid: [{ required: true, message: '请输入工号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

// k 账号首次登录 / 密码过期 → 强制改密弹窗状态
const changePwdFormRef = ref(null)
const changePwdDialog = reactive({
  visible: false,
  loading: false,
  title: '',
  pendingUserInfo: null,
  pendingTarget: '/home',
  form: {
    old_password: '',
    new_password: '',
    confirm_password: ''
  },
  rules: {
    old_password: [
      { required: true, message: '请输入旧密码', trigger: 'blur' }
    ],
    new_password: [
      { required: true, message: '请输入新密码', trigger: 'blur' },
      { min: 6, message: '新密码至少 6 位', trigger: 'blur' },
      {
        validator: (rule, value, cb) => {
          if (value && value === changePwdDialog.form.old_password) {
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
          if (value !== changePwdDialog.form.new_password) {
            return cb(new Error('两次输入的新密码不一致'))
          }
          cb()
        },
        trigger: 'blur'
      }
    ]
  }
})

// 登录成功后的统一跳转（强制改密完成后也走这条）
const navigateAfterLogin = (userInfo) => {
  const loginid = userInfo?.loginid || ''
  const target = loginid.startsWith('k') && loginid !== 'admin' ? '/collection-notes' : '/home'
  router.push(target)
}

const handleLogin = async () => {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    const res = await api.auth.login(form)
    if (!res.success) {
      ElMessage.error(res.message || '登录失败')
      return
    }

    // 先把登录态写进去（改密接口需要 X-User-Info 头）
    localStorage.setItem('user_info', JSON.stringify(res.user_info))
    ElMessage.success(res.message || '登录成功')

    // k 账号首次登录 / 密码过期 → 强制改密，不能直接跳转
    if (res.must_change_password) {
      changePwdDialog.title = '首次登录请修改密码'
      changePwdDialog.form.old_password = form.password // 默认密码场景下回填，简化用户输入
      changePwdDialog.form.new_password = ''
      changePwdDialog.form.confirm_password = ''
      changePwdDialog.pendingUserInfo = res.user_info
      changePwdDialog.pendingTarget = (res.user_info?.loginid || '').startsWith('k')
        && res.user_info?.loginid !== 'admin'
        ? '/collection-notes'
        : '/home'
      // 下一帧再打开，避免和上面的 ElMessage 抢占焦点
      setTimeout(() => {
        changePwdDialog.visible = true
      }, 0)
      return
    }

    navigateAfterLogin(res.user_info)
  } catch (error) {
    ElMessage.error(error.message || '登录失败')
  } finally {
    loading.value = false
  }
}

const submitChangePassword = async () => {
  const valid = await changePwdFormRef.value.validate().catch(() => false)
  if (!valid) return

  changePwdDialog.loading = true
  try {
    const res = await api.auth.changePassword({
      old_password: changePwdDialog.form.old_password,
      new_password: changePwdDialog.form.new_password
    })
    if (!res.success) {
      ElMessage.error(res.message || '密码修改失败')
      return
    }
    // 把后端返回的新过期时间戳写回 localStorage，免得路由守卫误判
    if (res.password_expire_at !== undefined) {
      const stored = JSON.parse(localStorage.getItem('user_info') || '{}')
      stored.password_expire_at = res.password_expire_at
      localStorage.setItem('user_info', JSON.stringify(stored))
      changePwdDialog.pendingUserInfo = {
        ...changePwdDialog.pendingUserInfo,
        password_expire_at: res.password_expire_at
      }
    }
    ElMessage.success('密码已修改')
    changePwdDialog.visible = false
    navigateAfterLogin(changePwdDialog.pendingUserInfo)
  } catch (error) {
    ElMessage.error(error.message || '密码修改失败')
  } finally {
    changePwdDialog.loading = false
  }
}

// 改密弹窗里的「返回登录」：清掉登录态、关弹窗、重置表单
const handleBackToLoginFromDialog = () => {
  changePwdDialog.visible = false
  api.auth.logout()
  form.loginid = ''
  form.password = ''
  // 清掉弹窗里残留的旧/新密码
  changePwdDialog.form.old_password = ''
  changePwdDialog.form.new_password = ''
  changePwdDialog.form.confirm_password = ''
}
</script>

<style scoped>
.login-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: var(--va-paper);
  /* 编辑风发丝网格 */
  background-image:
    linear-gradient(var(--va-hairline) 1px, transparent 1px),
    linear-gradient(90deg, var(--va-hairline) 1px, transparent 1px);
  background-size: 56px 56px;
  background-position: center;
  position: relative;
}

.login-container::before {
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(ellipse 70% 60% at 50% 45%, var(--va-paper) 30%, transparent 75%);
  pointer-events: none;
}

.login-box {
  position: relative;
  width: 400px;
  padding: 48px 44px 40px;
  background: #fff;
  border: 1px solid var(--va-hairline);
  border-radius: var(--va-radius-md);
  box-shadow: 0 2px 6px rgba(33, 29, 24, 0.05), 0 16px 48px rgba(33, 29, 24, 0.07);
}

.login-box::before {
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
  margin-bottom: 32px;
}

.brand-icon {
  color: var(--va-accent);
}

.title {
  margin: 14px 0 8px;
  font-family: var(--va-font-display);
  font-size: 26px;
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

.login-form {
  margin-top: 8px;
}

.login-button {
  width: 100%;
  letter-spacing: 0.3em;
  text-indent: 0.3em;
  font-weight: 600;
}

.footer-note {
  position: relative;
  margin-top: 28px;
  font-size: 12px;
  color: var(--va-muted);
  letter-spacing: 0.2em;
}

.password-toggle {
  cursor: pointer;
  color: var(--va-muted);
}

.password-toggle:hover {
  color: var(--va-accent);
}
</style>