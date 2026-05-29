<script setup>
import { computed } from "vue";
import { useRoute } from "vue-router";
import StudentLayout from "@/components/StudentLayout.vue";

const route = useRoute();
const quizHref = computed(() => {
  const code = route.query.code ? `?code=${encodeURIComponent(route.query.code)}` : "";
  return `/student/quiz${code}`;
});
</script>

<template>
  <StudentLayout title="Join Quiz">
    <main class="mx-auto max-w-lg px-4 py-12 text-center">
      <p class="text-slate-600">
        Enter the join code from your teacher, or continue directly if you opened a shared link.
      </p>
      <router-link :to="quizHref" class="btn-primary mt-8 inline-flex px-8">
        Continue to student quiz
      </router-link>
    </main>
  </StudentLayout>
</template>
