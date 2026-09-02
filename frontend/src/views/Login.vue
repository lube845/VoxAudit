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
            placeholder="OA密码"
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

const handleLogin = async () => {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    const res = await api.auth.login(form)
    if (res.success) {
      localStorage.setItem('user_info', JSON.stringify(res.user_info))
      ElMessage.success(res.message || '登录成功')
      router.push('/home')
    } else {
      ElMessage.error(res.message || '登录失败')
    }
  } catch (error) {
    ElMessage.error(error.message || '登录失败')
  } finally {
    loading.value = false
  }
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