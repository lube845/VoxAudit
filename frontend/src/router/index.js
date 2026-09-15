import { createRouter, createWebHistory } from 'vue-router'
import api from '@/api'
import { audit } from '@/utils/audit'

// k 账号（客服）可访问的页面白名单
const K_ALLOWED_PATHS = ['/collection-notes', '/rules', '/recordings']

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue')
  },
  {
    // 强制改密页：与 Layout 平级，不进主框架；路由守卫强制 k 账号必走此页
    path: '/change-password',
    name: 'ChangePassword',
    component: () => import('@/views/ChangePassword.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/',
    name: 'Layout',
    component: () => import('@/views/Layout.vue'),
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        redirect: '/home'
      },
      {
        path: '/home',
        name: 'Home',
        component: () => import('@/views/Home.vue')
      },
      {
        path: '/rules',
        name: 'Rules',
        component: () => import('@/views/Rules.vue')
      },
      {
        path: '/recordings',
        name: 'Recordings',
        component: () => import('@/views/Recordings.vue')
      },
      {
        path: '/collection-notes',
        name: 'CollectionNotes',
        component: () => import('@/views/CollectionNotes.vue')
      },
      {
        path: '/recordings/:id',
        name: 'RecordingDetail',
        component: () => import('@/views/RecordingDetail.vue')
      },
      {
        path: '/export',
        name: 'Export',
        component: () => import('@/views/Export.vue')
      },
      {
        path: '/storage',
        name: 'Storage',
        component: () => import('@/views/StorageCleanup.vue'),
        meta: { requiresAdmin: true }
      },
      {
        path: '/user-management',
        name: 'UserManagement',
        component: () => import('@/views/UserManagement.vue'),
        meta: { requiresAdmin: true },
        redirect: '/user-management/stats',
        children: [
          {
            path: 'stats',
            name: 'UserStats',
            component: () => import('@/views/UserStats.vue'),
            meta: { requiresAdmin: true }
          },
          {
            path: 'k-users',
            name: 'CustomerService',
            component: () => import('@/views/CustomerServiceManagement.vue'),
            meta: { requiresAdmin: true }
          }
        ]
      },
      {
        path: '/system-settings',
        name: 'SystemSettings',
        component: () => import('@/views/SystemSettings.vue'),
        meta: { requiresAdmin: true }
      },
      {
        path: '/audit-logs',
        name: 'AuditLogs',
        component: () => import('@/views/AuditLogs.vue'),
        meta: { requiresAdmin: true }
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  const userInfo = api.auth.getUserInfo()
  const loginid = userInfo?.loginid || ''
  // k 开头的普通账号只能访问催记管理
  const isKUser = loginid.startsWith('k') && loginid !== 'admin'

  // k 账号的密码是否需要强制修改：
  //   - password_expire_at 缺失/为 null → 仍在用默认密码
  //   - password_expire_at < now → 已过 3 个月有效期
  // （admin / OA 用户没有此字段，恒为 false）
  let mustChangePassword = false
  if (isKUser && userInfo) {
    const exp = userInfo.password_expire_at
    if (exp === null || exp === undefined) {
      mustChangePassword = true
    } else {
      mustChangePassword = Number(exp) * 1000 < Date.now()
    }
  }

  if (to.meta.requiresAuth && !userInfo) {
    next('/login')
  } else if (isKUser && mustChangePassword && to.path !== '/change-password') {
    // 密码需强制修改（默认密码 / 3 个月过期）→ 拦截到改密页
    // 优先于「已登录就跳走」判断：避免刷新时先闪到 /login 或 /collection-notes
    next({ path: '/change-password', query: { redirect: to.fullPath } })
  } else if (to.path === '/login' && userInfo) {
    next(isKUser ? '/collection-notes' : '/home')
  } else if (isKUser && !mustChangePassword && to.path === '/change-password') {
    // 密码已正常 → 离开改密页
    next('/collection-notes')
  } else if (isKUser && !mustChangePassword && !K_ALLOWED_PATHS.some(p => to.path === p || to.path.startsWith(p + '/'))) {
    // k 用户访问白名单之外的页面 → 重定向到催记管理
    // （密码正常时；如果密码还要改，让上面那条接管，避免死循环）
    next('/collection-notes')
  } else if (to.meta.requiresAdmin && loginid !== 'admin') {
    next(isKUser ? '/collection-notes' : '/home')
  } else {
    next()
  }
})

export default router

// ——— 路由守卫：每次路由切换记录 page.view ———
router.afterEach((to, from) => {
  // 不记登录页（避免刷一堆 page.view 噪音）
  if (to.path === '/login') return

  const userInfo = api.auth.getUserInfo()
  if (!userInfo) return  // 未登录不记

  // 从路由路径推断 target_type
  // 例：/rules → "rule"，/user-management/k-users → "k_user"，/recordings/123 → "recording_detail"
  const segments = to.path.split('/').filter(Boolean)
  if (!segments.length) return

  const seg0 = segments[0]
  const seg1 = segments[1]
  let targetType = seg0
  if (seg0 === 'recordings' && segments.length > 1) {
    targetType = 'recording_detail'
  } else if (seg0 === 'user-management' && seg1 === 'k-users') {
    targetType = 'k_user'
  } else if (seg0 === 'user-management' && seg1 === 'stats') {
    targetType = 'user_stats'
  } else if (seg0 === 'collection-notes') {
    targetType = 'collection_note'
  }
  // target_id 用完整路由路径（含 query）
  const targetId = to.fullPath

  audit('page.view', targetType, targetId, {
    from: from.fullPath || '',
  })
})