export function speakText(text, { lang = "en-US", rate = 0.95 } = {}) {
  if (typeof window === "undefined" || !window.speechSynthesis) return;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = lang;
  utterance.rate = rate;
  window.speechSynthesis.speak(utterance);
}

export function speakNextQuestion() {
  speakText("Next question");
}

export function speakQuizEnded() {
  speakText("The Quiz has ended. Thanks for your participation.");
}
