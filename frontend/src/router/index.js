import { createRouter, createWebHistory } from "vue-router";
import LoginView from "@/views/LoginView.vue";
import TeacherHome from "@/views/teacher/HomeView.vue";
import BanksView from "@/views/teacher/BanksView.vue";
import SessionView from "@/views/teacher/SessionView.vue";
import StudentJoin from "@/views/student/JoinView.vue";
import QuizView from "@/views/student/QuizView.vue";
import ReviewView from "@/views/student/ReviewView.vue";
import HistoryView from "@/views/student/HistoryView.vue";
import { getLoginSession } from "@/composables/useAuth";

function entryRouteForRole(role) {
  return role === "teacher" ? "/teacher" : "/student";
}

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", redirect: "/login" },
    { path: "/login", name: "login", component: LoginView },
    { path: "/teacher", name: "teacher", component: TeacherHome, meta: { requiresAuth: true, role: "teacher" } },
    { path: "/teacher/banks", name: "teacher-banks", component: BanksView, meta: { requiresAuth: true, role: "teacher" } },
    { path: "/teacher/session/:sessionId", name: "teacher-session", component: SessionView, meta: { requiresAuth: true, role: "teacher" } },
    { path: "/student", name: "student", component: StudentJoin, meta: { requiresAuth: true, role: "student" } },
    { path: "/student/quiz", name: "student-quiz", component: QuizView, meta: { requiresAuth: true, role: "student" } },
    { path: "/student/review", name: "student-review", component: ReviewView, meta: { requiresAuth: true, role: "student" } },
    { path: "/student/history", name: "student-history", component: HistoryView, meta: { requiresAuth: true, role: "student" } },
  ],
});

router.beforeEach((to) => {
  const session = getLoginSession();
  const requiresAuth = Boolean(to.meta.requiresAuth);
  const requiredRole = to.meta.role;

  if (!session) {
    if (requiresAuth) {
      return {
        path: "/login",
        query: { next: to.fullPath },
      };
    }
    return true;
  }

  if (to.path === "/login") {
    return entryRouteForRole(session.role);
  }

  if (requiresAuth && requiredRole && session.role !== requiredRole) {
    return entryRouteForRole(session.role);
  }

  return true;
});

export default router;
