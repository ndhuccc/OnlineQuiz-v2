<script setup>
import katex from "katex";
import { onMounted, ref, watch } from "vue";

const props = defineProps({
  content: { type: String, default: "" },
  block: { type: Boolean, default: false },
  textClass: { type: String, default: "" },
});

const root = ref(null);

function renderLatex(text) {
  if (!text) return "";
  let html = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  html = html.replace(/\$\$([\s\S]+?)\$\$/g, (_, tex) => {
    try {
      return katex.renderToString(tex.trim(), { displayMode: true, throwOnError: false });
    } catch {
      return `<span class="text-red-500">[LaTeX]</span>`;
    }
  });

  html = html.replace(/\$([^$\n]+?)\$/g, (_, tex) => {
    try {
      return katex.renderToString(tex.trim(), { displayMode: false, throwOnError: false });
    } catch {
      return `$${tex}$`;
    }
  });

  return html.replace(/\n/g, "<br />");
}

function render() {
  if (!root.value) return;
  root.value.innerHTML = renderLatex(props.content);
}

watch(() => props.content, render);
onMounted(render);
</script>

<template>
  <div
    ref="root"
    class="math-content leading-relaxed"
    :class="[block ? 'text-base' : 'text-sm', textClass]"
  />
</template>

<style>
.math-content .katex-display {
  margin: 0.75em 0;
  overflow-x: auto;
  overflow-y: hidden;
}
</style>
