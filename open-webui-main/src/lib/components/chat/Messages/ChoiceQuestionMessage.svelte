<script lang="ts">
  import { List } from 'lucide-svelte';
  export let message;
  export let readOnly = false;

  let selectedIndex = null;
  let feedback = '';

  const selectOption = (index: number) => {
    if (readOnly || selectedIndex !== null) return;
    selectedIndex = index;
    const isCorrect = index === message.answer;
    feedback = isCorrect ? '✅ 选择正确' : '❌ 选择错误';
  };

  const isCorrect = (i) => i === message.answer;
  const isSelected = (i) => i === selectedIndex;
</script>

<style>
  .header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-weight: 600;
    font-size: 1.125rem;
    color: var(--muted-foreground);
    margin-bottom: 0.5rem;
    line-height: 0.1;
  }

  button.choice-button {
    transition: all 0.2s ease;
  }

  button.choice-button:not(:disabled):hover {
    background-color: #f3f4f6; /* hover 淡灰色 */
    border-color: #d1d5db;
  }

  /* 针对 dark 模式下 hover */
  @media (prefers-color-scheme: dark) {
    button.choice-button:not(:disabled):hover {
      background-color: #ae82ef; /* hover 深灰 */
      color: #fff;
    }
  }
</style>
  <div class="header">
    <List class="w-5 h-5 text-primary" />
    单选题
  </div>
  <div class="bg-muted p-4 rounded-lg shadow w-full space-y-4">
    <div class="text-base font-semibold text-foreground">{message.question}</div>

    <div class="flex flex-col gap-2">
      {#each message.options as option, i}
        <button
          class="choice-button px-4 py-2 text-left rounded-md border text-sm font-medium
            {selectedIndex !== null
              ? isCorrect(i)
                ? 'bg-green-100 text-green-900 border-green-400'
                : isSelected(i)
                  ? 'bg-red-100 text-red-900 border-red-400'
                  : 'bg-white text-black border-neutral-300'
              : 'bg-white text-black border-neutral-300'}"
          on:click={() => selectOption(i)}
          disabled={readOnly || selectedIndex !== null}
        >
          {option}
        </button>
      {/each}
    </div>

    {#if selectedIndex !== null}
      <div class="text-sm mt-3 space-y-1">
        <div class="font-medium {feedback.includes('正确') ? 'text-green-600' : 'text-red-600'}">
          {feedback}
        </div>
        
        {#if selectedIndex !== message.answer}
          <div class="text-neutral-700">
            正确答案是：<strong>{message.options[message.answer]}</strong>
          </div>
        {/if}

        {#if message.explanation}
          <div class="mt-1 text-muted-foreground italic">{message.explanation}</div>
        {/if}
      </div>
    {/if}
  </div>