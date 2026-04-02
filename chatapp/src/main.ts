import { createApp } from 'vue';
import App from './App.vue';
import router from './router';
import store from './store';

import './tailwind.css';

const app = createApp(App);

// Load persisted user state before mounting.
store.dispatch('loadUserState');

window.addEventListener('storage', (event) => {
  if (event.key !== 'echoisle_logout_signal' || !event.newValue) {
    return;
  }
  store.dispatch('logout', { skipRemote: true, emitSignal: false });
  if (router.currentRoute.value.path !== '/login') {
    router.replace('/login');
  }
});

app.use(store);
app.use(router);

store.dispatch('appStart');

app.mount('#app');
