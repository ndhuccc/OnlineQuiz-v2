<script setup>
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import TeacherLayout from "@/components/TeacherLayout.vue";
import { saveHostSession } from "@/composables/useAuth";
import { parseJsonResponse } from "@/utils/parseJsonResponse";

const router = useRouter();

const banks = ref([]);
const loading = ref(false);
const message = ref("");
const error = ref("");
const fileInput = ref(null);

const form = ref({
  name: "",
  default_points: 1,
  default_timer_seconds: 90,
  file: null,
});

async function loadBanks() {
  loading.value = true;
  error.value = "";
  try {
    const res = await fetch("/api/question-banks/");
    const data = await parseJsonResponse(res);
    if (!res.ok) throw new Error(data.detail || "無法載入題庫。");
    banks.value = data;
  } catch (e) {
    error.value = String(e);
  } finally {
    loading.value = false;
  }
}

function onFileChange(event) {
  form.value.file = event.target.files?.[0] ?? null;
}

function parseImportError(data) {
  if (Array.isArray(data?.errors) && data.errors.length > 0) {
    const first = data.errors[0];
    return `${data.detail || "Import failed."} Row ${first.index + 1}: ${first.message}`;
  }
  return data?.detail || "Import failed.";
}

function parseDeleteError(data, bankName) {
  if (data?.detail) {
    return `Failed to delete "${bankName}": ${data.detail}`;
  }
  return `Failed to delete "${bankName}".`;
}

async function uploadJson() {
  const selectedFile = fileInput.value?.files?.[0] ?? form.value.file;
  form.value.file = selectedFile ?? null;

  if (!selectedFile) {
    error.value = "Please choose a JSON file.";
    return;
  }
  if (selectedFile.size === 0) {
    error.value = "The selected JSON file is empty. Please choose a file with at least one question.";
    return;
  }

  loading.value = true;
  error.value = "";
  message.value = "";

  try {
    const fd = new FormData();
    fd.append("file", selectedFile);
    if (form.value.name) fd.append("name", form.value.name);
    fd.append("default_points", String(form.value.default_points));
    fd.append("default_timer_seconds", String(form.value.default_timer_seconds));

    const res = await fetch("/api/question-banks/", { method: "POST", body: fd });
    const data = await parseJsonResponse(res);
    if (!res.ok) throw new Error(parseImportError(data));

    const importedCount = data.import_report?.imported_count ?? data.question_count ?? 0;
    message.value = `Imported "${data.name}" with ${importedCount} question(s).`;
    form.value.file = null;
    if (fileInput.value) fileInput.value.value = "";
    await loadBanks();
  } catch (e) {
    error.value = String(e);
  } finally {
    loading.value = false;
  }
}

async function startSession(bankId) {
  loading.value = true;
  error.value = "";
  try {
    const res = await fetch("/api/sessions/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ bank_id: bankId }),
    });
    const data = await parseJsonResponse(res);
    if (!res.ok) throw new Error(data.detail || "Failed to create session.");
    saveHostSession(data.id, data.host_token);
    router.push({ name: "teacher-session", params: { sessionId: data.id } });
  } catch (e) {
    error.value = String(e);
  } finally {
    loading.value = false;
  }
}

async function deleteBank(id, name) {
  if (!confirm(`Delete question bank "${name}"?`)) return;
  loading.value = true;
  error.value = "";
  message.value = "";
  try {
    const res = await fetch(`/api/question-banks/${id}/`, { method: "DELETE" });
    const data = await parseJsonResponse(res).catch(() => ({}));
    if (!res.ok) throw new Error(parseDeleteError(data, name));
    message.value = `Question bank "${name}" deleted.`;
    await loadBanks();
  } catch (e) {
    error.value = String(e);
  } finally {
    loading.value = false;
  }
}

onMounted(loadBanks);
</script>

<template>
  <TeacherLayout title="Question Banks">
    <main class="mx-auto max-w-2xl px-4 pb-10 pt-4">
      <section class="card">
        <h2 class="mb-3 font-semibold">Import JSON Question Bank</h2>
        <div class="space-y-3">
          <label class="block">
            <span class="text-sm text-slate-600">Question bank name</span>
            <input
              v-model="form.name"
              type="text"
              class="mt-1 w-full rounded border px-3 py-2"
              placeholder="Midterm practice"
            />
          </label>

          <div class="flex gap-4">
            <label class="block flex-1">
              <span class="text-sm text-slate-600">Default points</span>
              <input
                v-model.number="form.default_points"
                type="number"
                min="0.1"
                step="0.1"
                class="mt-1 w-full rounded border px-3 py-2"
              />
            </label>

            <label class="block flex-1">
              <span class="text-sm text-slate-600">Default timer (seconds)</span>
              <input
                v-model.number="form.default_timer_seconds"
                type="number"
                min="5"
                class="mt-1 w-full rounded border px-3 py-2"
              />
            </label>
          </div>

          <input
            ref="fileInput"
            type="file"
            accept=".json,application/json"
            @change="onFileChange"
          />
          <p v-if="form.file" class="text-sm text-slate-500">
            Selected file: {{ form.file.name }}
          </p>

          <button
            type="button"
            class="min-h-[44px] w-full rounded-lg bg-indigo-600 px-4 py-2 text-white disabled:opacity-50"
            :disabled="loading"
            @click="uploadJson"
          >
            {{ loading ? "Importing..." : "Import question bank" }}
          </button>
        </div>
      </section>

      <p v-if="message" class="mt-4 rounded bg-green-50 p-3 text-green-800">{{ message }}</p>
      <p v-if="error" class="mt-4 rounded bg-red-50 p-3 text-red-800">{{ error }}</p>

      <section class="mt-8">
        <h2 class="mb-3 font-semibold">Available Banks</h2>
        <p v-if="loading && !banks.length" class="text-slate-500">Loading...</p>
        <ul v-else-if="banks.length" class="space-y-2">
          <li
            v-for="bank in banks"
            :key="bank.id"
            class="flex items-center justify-between rounded-lg border bg-white p-4"
          >
            <div>
              <p class="font-medium">{{ bank.name }}</p>
              <p class="text-sm text-slate-500">
                {{ bank.question_count }} question(s), {{ bank.default_points }} point(s),
                {{ bank.default_timer_seconds }} second(s)
              </p>
            </div>

            <div class="flex gap-2">
              <button
                type="button"
                class="min-h-[44px] rounded-lg bg-indigo-600 px-3 text-white"
                @click="startSession(bank.id)"
              >
                Start
              </button>
              <button
                type="button"
                class="min-h-[44px] rounded px-3 text-red-600 hover:bg-red-50"
                @click="deleteBank(bank.id, bank.name)"
              >
                Delete
              </button>
            </div>
          </li>
        </ul>
        <p v-else class="text-slate-500">No question banks yet.</p>
      </section>
    </main>
  </TeacherLayout>
</template>
