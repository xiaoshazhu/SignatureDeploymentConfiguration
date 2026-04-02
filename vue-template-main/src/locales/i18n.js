import { createI18n } from 'vue-i18n'
import en from './en.json';
import zh from './zh.json';
import ja from './ja.json';
import { bitable } from '@lark-base-open/js-sdk'

export const i18n = createI18n({
  locale: 'zh', // 默认初识为中文或从SDK动态设置
  legacy: false, // 使用 Composition API 模式
  allowComposition: true,
  messages: {
    en: en,
    zh: zh,
    ja: ja
  }
})

// 动态通过 SDK 获取语言设置并切换
const updateLanguage = async () => {
  try {
    const lang = await bitable.bridge.getLanguage();
    console.info('[i18n] Bitable language detected:', lang);
    
    if (lang.startsWith('zh')) {
      i18n.global.locale.value = 'zh'
    } else if (lang.startsWith('ja')) {
      i18n.global.locale.value = 'ja'
    } else {
      i18n.global.locale.value = 'en'
    }
  } catch (e) {
    console.error('[i18n] Failed to sync language:', e);
  }
}

updateLanguage();

