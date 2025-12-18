import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'Login',
      component: () => import('@/views/LoginView.vue'),
    },
    {
      path: '/',
      name: 'Layout',
      component: () => import('@/layouts/MainLayout.vue'),
      redirect: '/graph',
      children: [
        {
          path: '/graph',
          name: 'Graph',
          component: () => import('@/views/GraphView.vue'),
        },
        {
          path: '/entities',
          name: 'Entities',
          component: () => import('@/views/EntitiesView.vue'),
        },
        {
          path: '/stats',
          name: 'Stats',
          component: () => import('@/views/StatsView.vue'),
        },
        {
          path: '/search',
          name: 'Search',
          component: () => import('@/views/SearchView.vue'),
        },
        {
          path: '/relations',
          name: 'Relations',
          component: () => import('@/views/RelationsView.vue'),
        },
        {
          path: '/system',
          name: 'System',
          component: () => import('@/views/SystemView.vue'),
        },
      ],
    },
  ],
})

// 路由守卫 - 检查认证
router.beforeEach((to, from, next) => {
  const key = localStorage.getItem('webui_key')

  if (to.name !== 'Login' && !key) {
    next({ name: 'Login' })
  } else if (to.name === 'Login' && key) {
    next({ name: 'Graph' })
  } else {
    next()
  }
})

export default router
