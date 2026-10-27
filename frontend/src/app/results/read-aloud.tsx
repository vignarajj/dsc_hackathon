"use client";

import { useEffect, useState, useSyncExternalStore } from "react";

import { speechChunks } from "@/lib/speech";

// Support never changes while the page is open, so there is nothing to subscribe to.
const noSubscription = () => () => {};
const canSpeak = () => "speechSynthesis" in window;
// The server cannot speak; the browser render then shows the button if it can.
const serverCanSpeak = () => false;

/** Read the text with the browser's own speech. Hidden where the browser cannot speak. */
export function ReadAloud({ text }: { text: string }) {
  const supported = useSyncExternalStore(noSubscription, canSpeak, serverCanSpeak);
  const [speaking, setSpeaking] = useState(false);

  // Stop when the text changes or the tab goes away, so speech never outlives its page.
  useEffect(
    () => () => {
      if (typeof window !== "undefined" && "speechSynthesis" in window) {
        window.speechSynthesis.cancel();
      }
    },
    [text],
  );

  if (!supported) {
    return null;
  }

  function start() {
    const chunks = speechChunks(text);
    if (chunks.length === 0) {
      return;
    }
    const synth = window.speechSynthesis;
    synth.cancel();
    // No language is set: the API does not report one, so the browser picks its default voice.
    chunks.forEach((chunk, index) => {
      const utterance = new SpeechSynthesisUtterance(chunk);
      utterance.onerror = () => setSpeaking(false);
      if (index === chunks.length - 1) {
        utterance.onend = () => setSpeaking(false);
      }
      synth.speak(utterance);
    });
    setSpeaking(true);
  }

  function stop() {
    window.speechSynthesis.cancel();
    setSpeaking(false);
  }

  return (
    <button
      type="button"
      onClick={speaking ? stop : start}
      disabled={!text.trim()}
      aria-pressed={speaking}
      className="rounded-full border border-line px-4 py-1.5 text-sm disabled:cursor-not-allowed disabled:opacity-40"
    >
      {speaking ? "Stop reading" : "Read aloud"}
    </button>
  );
}
