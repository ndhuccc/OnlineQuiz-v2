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

  // 1) Pull LaTeX blocks out and render them first; remember rendered HTML
  //    in `latexBlocks`, and leave a placeholder in the source string. This
  //    protects `&` (matrix column separator), `<`, `>` inside LaTeX from
  //    the HTML-escape step below.
  const latexBlocks = [];
  const stamp = (rendered) => {
    latexBlocks.push(rendered);
    return `\x00LATEX${latexBlocks.length - 1}\x00`;
  };

  let html = text.replace(/\$\$([\s\S]+?)\$\$/g, (_, tex) => {
    try {
      return stamp(katex.renderToString(tex.trim(), { displayMode: true, throwOnError: false }));
    } catch {
      return stamp(`<span class="text-red-500">[LaTeX]</span>`);
    }
  });

  html = html.replace(/\$([^$\n]+?)\$/g, (_, tex) => {
    try {
      return stamp(katex.renderToString(tex.trim(), { displayMode: false, throwOnError: false }));
    } catch {
      return stamp(`$${tex}$`);
    }
  });

  // 2) HTML-escape only the plain text portions (LaTeX is now placeholders).
  html = html.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  // 3) Re-substitute the rendered LaTeX blocks.
  html = html.replace(/\x00LATEX(\d+)\x00/g, (_, idx) => latexBlocks[Number(idx)]);

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
