<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { saveLoginSession, getLoginSession } from "@/composables/useAuth";
import { parseJsonResponse } from "@/utils/parseJsonResponse";

const router = useRouter();
const route = useRoute();
const role = ref("teacher");
const loading = ref(false);
const error = ref("");

const teacherForm = reactive({ username: "", password: "" });
const studentForm = reactive({ student_no: "", password: "" });

const title = computed(() => (role.value === "teacher" ? "Teacher Login" : "Student Login"));
const subtitle = computed(() =>
  role.value === "teacher"
    ? "Use your admin account to enter the teacher dashboard."
    : "Use your student number and password from the imported user database.",
);

async function submitLogin() {
  error.value = "";
  loading.value = true;
  try {
    const body =
      role.value === "teacher"
        ? { role: "teacher", username: teacherForm.username, password: teacherForm.password }
        : { role: "student", student_no: studentForm.student_no, password: studentForm.password };

    const res = await fetch("/api/auth/login/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await parseJsonResponse(res);
    if (!res.ok) throw new Error(data.detail || "Login failed.");

    saveLoginSession(data);
    await router.push(data.redirect_to || (data.role === "teacher" ? "/teacher" : "/student"));
  } catch (e) {
    error.value = String(e?.message || e);
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  const session = getLoginSession();
  if (session?.redirect_to) {
    router.replace(session.redirect_to);
    return;
  }

  if (route.query.role === "student") {
    role.value = "student";
  }
});
</script>

<template>
  <div class="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(79,70,229,0.18),_transparent_35%),linear-gradient(180deg,#f8fafc_0%,#e2e8f0_100%)] px-4 py-10 text-slate-900">
    <main class="mx-auto grid min-h-[calc(100vh-5rem)] max-w-5xl overflow-hidden rounded-[2rem] border border-white/60 bg-white/85 shadow-[0_30px_100px_rgba(15,23,42,0.18)] backdrop-blur md:grid-cols-[1.05fr_0.95fr]">
      <section class="relative flex flex-col justify-between overflow-hidden bg-slate-950 px-8 py-10 text-white md:px-10">
        <div class="absolute inset-0 bg-[linear-gradient(135deg,rgba(59,130,246,0.25),transparent_45%),linear-gradient(315deg,rgba(14,165,233,0.2),transparent_35%)]"></div>
        <div class="relative z-10 max-w-md">
          <p class="text-xs font-semibold uppercase tracking-[0.35em] text-cyan-300">OnlineQuiz</p>
          <h1 class="mt-4 text-4xl font-black tracking-tight md:text-5xl">Shared login for teachers and students</h1>
          <p class="mt-4 text-sm leading-6 text-slate-300">
            Teachers sign in with the Django admin account. Students sign in with their imported user profile.
          </p>
        </div>
        <div class="relative z-10 grid gap-3 text-sm text-slate-300 md:grid-cols-2">
          <div class="rounded-2xl border border-white/10 bg-white/5 p-4">
            <p class="font-semibold text-white">Teacher</p>
            <p class="mt-1">Username + password, then go straight to the teacher dashboard.</p>
          </div>
          <div class="rounded-2xl border border-white/10 bg-white/5 p-4">
            <p class="font-semibold text-white">Student</p>
            <p class="mt-1">Student number + password, then continue to the student entry flow.</p>
          </div>
        </div>
      </section>

      <section class="flex items-center px-6 py-10 md:px-10">
        <div class="w-full max-w-md">
          <div class="mb-6 flex rounded-2xl bg-slate-100 p-1">
            <button class="flex-1 rounded-xl px-4 py-3 text-sm font-semibold transition" :class="role === 'teacher' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500'" type="button" @click="role = 'teacher'">Teacher</button>
            <button class="flex-1 rounded-xl px-4 py-3 text-sm font-semibold transition" :class="role === 'student' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500'" type="button" @click="role = 'student'">Student</button>
          </div>

          <div class="mb-6">
            <h2 class="text-2xl font-bold tracking-tight">{{ title }}</h2>
            <p class="mt-2 text-sm text-slate-600">{{ subtitle }}</p>
          </div>

          <form class="space-y-4" @submit.prevent="submitLogin">
            <template v-if="role === 'teacher'">
              <label class="block">
                <span class="mb-1 block text-sm font-medium text-slate-700">Username</span>
                <input v-model="teacherForm.username" class="input-field" autocomplete="username" type="text" placeholder="ccchiang" />
              </label>
              <label class="block">
                <span class="mb-1 block text-sm font-medium text-slate-700">Password</span>
                <input v-model="teacherForm.password" class="input-field" autocomplete="current-password" type="password" placeholder="••••••••" />
              </label>
            </template>

            <template v-else>
              <label class="block">
                <span class="mb-1 block text-sm font-medium text-slate-700">Student No.</span>
                <input v-model="studentForm.student_no" class="input-field" autocomplete="username" type="text" placeholder="110001" />
              </label>
              <label class="block">
                <span class="mb-1 block text-sm font-medium text-slate-700">Password</span>
                <input v-model="studentForm.password" class="input-field" autocomplete="current-password" type="password" placeholder="••••••••" />
              </label>
            </template>

            <p v-if="error" class="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{{ error }}</p>

            <button class="btn-primary w-full justify-center" :disabled="loading" type="submit">
              {{ loading ? "Signing in..." : "Sign in" }}
            </button>
          </form>

          <p class="mt-6 text-xs leading-5 text-slate-500">
            Teachers are authenticated against Django users. Students are matched against the imported user database.
          </p>
        </div>
      </section>
    </main>
  </div>
</template>