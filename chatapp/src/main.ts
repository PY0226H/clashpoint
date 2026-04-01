import { createApp } from 'vue';
import App from './App.vue';
import router from './router';
import store from './store';

import './tailwind.css';

const app = createApp(App);

// Load persisted user state before mounting.
store.dispatch('loadUserState');

app.use(store);
app.use(router);

store.dispatch('appStart');

app.mount('#app');
