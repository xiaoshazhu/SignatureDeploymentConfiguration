import { createApp } from 'vue'
import App from './App.vue'
import ElementPlus from 'element-plus' // ⭐ 引入 Element Plus
import 'element-plus/dist/index.css' // ⭐ 引入样式
import VueSignaturePad from 'vue-signature-pad'; // ⭐ 引入
import { i18n } from './locales/i18n'
import './assets/main.css'

createApp(App)
    .use(i18n)
    .use(ElementPlus) // ⭐ 注册 Element Plus
    .use(VueSignaturePad) // ⭐ 注册
    .mount('#app')