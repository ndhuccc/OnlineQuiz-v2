<script setup>
import QRCode from "qrcode";
import { onMounted, ref, watch } from "vue";

const props = defineProps({
  joinCode: { type: String, required: true },
  joinUrl: { type: String, default: "" },
});

const qrDataUrl = ref("");
const copied = ref(false);

async function makeQr() {
  const url = props.joinUrl || `${location.origin}/student/quiz?code=${props.joinCode}`;
  try {
    qrDataUrl.value = await QRCode.toDataURL(url, { width: 200, margin: 2 });
  } catch {
    qrDataUrl.value = "";
  }
}

async function copyCode() {
  await navigator.clipboard.writeText(props.joinCode);
  copied.value = true;
  setTimeout(() => {
    copied.value = false;
  }, 2000);
}

watch(() => [props.joinCode, props.joinUrl], makeQr, { immediate: true });
onMounted(makeQr);
</script>

<template>
  <div class="rounded-xl border-2 border-dashed border-indigo-200 bg-indigo-50/50 p-4 text-center">
    <p class="mb-1 text-sm text-slate-600">Join Code</p>
    <p class="text-4xl font-bold tracking-[0.3em] text-indigo-700">{{ joinCode }}</p>
    <button type="button" class="mt-2 text-sm text-indigo-600 underline" @click="copyCode">
      {{ copied ? "Copied" : "Copy code" }}
    </button>
    <img
      v-if="qrDataUrl"
      :src="qrDataUrl"
      alt="QR Code"
      class="mx-auto mt-4 rounded-lg border bg-white p-2"
      width="200"
      height="200"
    />
    <p class="mt-2 break-all text-xs text-slate-500">{{ joinUrl }}</p>
  </div>
</template>
