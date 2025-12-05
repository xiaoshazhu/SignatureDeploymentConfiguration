<script setup>
import { ref, computed, onMounted } from 'vue';
import ConfigPanel from './components/ConfigPanel.vue';
import SignPage from './components/SignPage.vue';

const currentPath = ref(window.location.pathname);

const isSignPage = computed(() => {
  return currentPath.value.startsWith('/sign');
});

// Handle browser back/forward
onMounted(() => {
  window.addEventListener('popstate', () => {
    currentPath.value = window.location.pathname;
  });
});
</script>

<template>
  <main>
    <SignPage v-if="isSignPage" />
    <ConfigPanel v-else />
  </main>
</template>

<style scoped>
  main {
    padding: 0;
    min-height: 100vh;
    background-color: var(--el-bg-color);
  }
</style>