<script setup>
import { useRouter } from "vue-router";
import { clearClientToken, clearLoginSession } from "@/composables/useAuth";

defineProps({
  title: { type: String, default: "學生端" },
});

const router = useRouter();

function logout() {
  clearLoginSession();
  clearClientToken();
  router.push("/login");
}
</script>

<template>
  <div class="min-h-screen bg-gradient-to-b from-indigo-50 to-slate-100">
    <header class="border-b border-indigo-100 bg-white/90 px-4 py-3 backdrop-blur">
      <div class="mx-auto flex max-w-4xl items-center justify-between">
        <div>
          <p class="text-xs font-medium text-indigo-600">OnlineQuiz 學生</p>
          <h1 class="text-lg font-bold">{{ title }}</h1>
        </div>
        <div class="flex items-center gap-4 text-sm">
          <router-link to="/student" class="text-slate-600 hover:text-indigo-600 font-medium">
            加入測驗
          </router-link>
          <router-link to="/student/history" class="text-slate-600 hover:text-indigo-600 font-medium">
            測驗紀錄
          </router-link>
          <button type="button" class="text-slate-600 hover:text-indigo-600 font-medium" @click="logout">
            Logout
          </button>
        </div>
      </div>
    </header>
    <slot />
  </div>
</template>
