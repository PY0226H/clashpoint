import { createRouter, createWebHistory } from 'vue-router';
import Login from '../views/Login.vue';
import Register from '../views/Register.vue';
import Chat from '../views/Chat.vue';
import JudgeReport from '../views/JudgeReport.vue';
import DebateLobby from '../views/DebateLobby.vue';
import DebateRoom from '../views/DebateRoom.vue';
import Wallet from '../views/Wallet.vue';

const routes = [
  { path: '/', name: 'Chat', component: Chat, meta: { requiresAuth: true } },
  { path: '/debate', name: 'DebateLobby', component: DebateLobby, meta: { requiresAuth: true } },
  { path: '/debate/sessions/:id', name: 'DebateRoom', component: DebateRoom, meta: { requiresAuth: true } },
  { path: '/judge-report', name: 'JudgeReport', component: JudgeReport, meta: { requiresAuth: true } },
  { path: '/wallet', name: 'Wallet', component: Wallet, meta: { requiresAuth: true } },
  { path: '/login', name: 'Login', component: Login },
  { path: '/register', name: 'Register', component: Register },

];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

// Navigation guard for authenticated routes
router.beforeEach((to, from, next) => {
  const isAuthenticated = !!localStorage.getItem('user');
  if (to.matched.some((record) => record.meta.requiresAuth) && !isAuthenticated) {
    next({ name: 'Login' });
  } else {
    next();
  }
});

export default router;
