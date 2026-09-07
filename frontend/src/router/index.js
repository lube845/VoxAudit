import { createRouter, createWebHistory } from 'vue-router'
import api from '@/api'

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
  } else if (isKUser && !mustChangePassword && to.path !== '/collection-notes' && !to.path.startsWith('/collection-notes')) {
    // k 用户访问任何非催记管理页面 → 重定向
    // （密码正常时；如果密码还要改，让上面那条接管，避免死循环）
    next('/collection-notes')
  } else if (to.meta.requiresAdmin && loginid !== 'admin') {
    next(isKUser ? '/collection-notes' : '/home')
  } else {
    next()
  }
})

export default router