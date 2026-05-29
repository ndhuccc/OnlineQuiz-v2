import { createRouter, createWebHistory } from "vue-router";
import TeacherHome from "@/views/teacher/HomeView.vue";
import BanksView from "@/views/teacher/BanksView.vue";
import SessionView from "@/views/teacher/SessionView.vue";
import StudentJoin from "@/views/student/JoinView.vue";
import QuizView from "@/views/student/QuizView.vue";
import ReviewView from "@/views/student/ReviewView.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", redirect: "/teacher" },
    { path: "/teacher", name: "teacher", component: TeacherHome },
    { path: "/teacher/banks", name: "teacher-banks", component: BanksView },
    { path: "/teacher/session/:sessionId", name: "teacher-session", component: SessionView },
    { path: "/student", name: "student", component: StudentJoin },
    { path: "/student/quiz", name: "student-quiz", component: QuizView },
    { path: "/student/review", name: "student-review", component: ReviewView },
  ],
});

export default router;
