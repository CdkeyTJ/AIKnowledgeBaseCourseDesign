<script lang="ts">
  import { CheckCheck } from 'lucide-svelte';
  export let message;
  export let readOnly = false;

  let selected = null;
  let feedback = '';

  const select = (value: boolean) => {
    if (readOnly || selected !== null) return;
    selected = value;
    feedback = value === message.content.answer ? '✅ 判断正确' : '❌ 判断错误';
  };

  const isCorrect = (v) => v === message.content.answer;
  const isSelected = (v) => v === selected;
</script>

<style>
  button.choice-button {
    transition: all 0.2s ease;
  }

  button.choice-button:not(:disabled):hover {
    background-color: #f3f4f6; /* 浅灰 hover */
    border-color: #d1d5db;
  }

  @media (prefers-color-scheme: dark) {
    button.choice-button:not(:disabled):hover {
      background-color: #ae82ef; /* 与 choice 一致的紫灰色 hover */
      color: #fff;
    }
  }
</style>

<div class="pt-6">
<div class="flex items-center gap-2 text-lg text-muted-foreground font-semibold mb-2">
  <CheckCheck class="w-5 h-5 text-primary" />
  判断题
</div>

<div class="bg-muted p-4 rounded-lg shadow w-full space-y-4">
  <div class="text-base font-semibold text-foreground">{message.content.question}</div>

  <div class="flex gap-4">
    <button
      class="choice-button px-4 py-2 text-center rounded-md border text-sm font-medium
        {selected !== null
          ? isCorrect(true)
            ? isSelected(true)
              ? 'bg-green-100 text-green-900 border-green-400'
              : 'bg-white text-black border-neutral-300'
            : isSelected(true)
              ? 'bg-red-100 text-red-900 border-red-400'
              : 'bg-white text-black border-neutral-300'
          : 'bg-white text-black border-neutral-300'}"
      on:click={() => select(true)}
      disabled={readOnly || selected !== null}
    >
      正确
    </button>

    <button
      class="choice-button px-4 py-2 text-center rounded-md border text-sm font-medium
        {selected !== null
          ? isCorrect(false)
            ? isSelected(false)
              ? 'bg-green-100 text-green-900 border-green-400'
              : 'bg-white text-black border-neutral-300'
            : isSelected(false)
              ? 'bg-red-100 text-red-900 border-red-400'
              : 'bg-white text-black border-neutral-300'
          : 'bg-white text-black border-neutral-300'}"
      on:click={() => select(false)}
      disabled={readOnly || selected !== null}
    >
      错误
    </button>
  </div>

  {#if selected !== null}
    <div class="text-sm mt-3 space-y-1">
      <div class="font-medium {feedback.includes('正确') ? 'text-green-600' : 'text-red-600'}">
        {feedback}
      </div>

      {#if selected !== message.content.answer}
        <div class="text-neutral-700">
          正确答案是：<strong>{message.content.answer ? '正确' : '错误'}</strong>
        </div>
      {/if}

      {#if message.content.explanation}
        <div class="mt-1 text-muted-foreground italic">{message.content.explanation}</div>
      {/if}
    </div>
  {/if}
</div>
</div>
