<script setup>
import { useRouter } from "vue-router";
import { clearLoginSession } from "@/composables/useAuth";

defineProps({
  title: { type: String, default: "Teacher" },
});

const router = useRouter();

function logout() {
  clearLoginSession();
  router.push("/login");
}
</script>

<template>
  <div class="min-h-screen bg-gradient-to-b from-slate-100 to-slate-200">
    <header class="border-b border-slate-200 bg-white/90 backdrop-blur">
      <div class="mx-auto flex max-w-4xl items-center justify-between px-4 py-3">
        <div>
          <p class="text-xs font-medium uppercase tracking-wide text-indigo-600">OnlineQuiz</p>
          <h1 class="text-lg font-bold text-slate-900">{{ title }}</h1>
        </div>
        <nav class="flex gap-3 text-sm">
          <router-link to="/teacher" class="text-slate-600 hover:text-indigo-600">
            Home
          </router-link>
          <router-link to="/teacher/banks" class="text-slate-600 hover:text-indigo-600">
            Banks
          </router-link>
          <button type="button" class="text-slate-600 hover:text-indigo-600" @click="logout">
            Logout
          </button>
        </nav>
      </div>
    </header>
    <slot />
  </div>
</template>
