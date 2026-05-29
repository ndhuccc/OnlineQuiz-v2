<script setup>
defineProps({
  title: { type: String, default: "學生端" },
});
</script>

<template>
  <div class="min-h-screen bg-gradient-to-b from-indigo-50 to-slate-100">
    <header class="border-b border-indigo-100 bg-white/90 px-4 py-3 backdrop-blur">
      <p class="text-xs font-medium text-indigo-600">OnlineQuiz 學生</p>
      <h1 class="text-lg font-bold">{{ title }}</h1>
    </header>
    <slot />
  </div>
</template>
