<script lang="ts">
  import { CheckSquare } from 'lucide-svelte';
  export let message;
  export let readOnly = false;

  let selectedIndices: number[] = [];
  let submitted = false;
  let feedback = '';

  function toggleOption(i: number) {
    if (readOnly || submitted) return;
    if (selectedIndices.includes(i)) {
      selectedIndices = selectedIndices.filter(x => x !== i);
    } else {
      selectedIndices = [...selectedIndices, i];
    }
  }

  function submit() {
    if (readOnly || submitted) return;
    submitted = true;

    const correct = [...message.content.answer].sort();
    const selected = [...selectedIndices].sort();
    const intersection = selected.filter(x => correct.includes(x));

    if (JSON.stringify(correct) === JSON.stringify(selected)) {
      feedback = "✅ 全部选择正确";
    } else if (intersection.length > 0) {
      feedback = "⚠️ 不完全正确";
    } else {
      feedback = "❌ 完全不正确";
    }
  }

  // 动态类名
  $: feedbackClass =
    feedback.includes("全部选择正确")
      ? "correct"
      : feedback.includes("不完全正确")
      ? "partial"
      : "wrong";
</script>

<style>
  .choice-container {
    padding-top: 1.5rem;
  }
  .header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-weight: 600;
    font-size: 1.125rem;
    color: var(--muted-foreground);
    margin-bottom: 0.5rem;
  }
  button.choice-button {
    border: 1px solid #ccc;
    background-color: white;
    color: black;
    padding: 8px 16px;
    margin-bottom: 8px;
    width: 100%;
    text-align: left;
    cursor: pointer;
    transition: background-color 0.2s, border-color 0.2s;
    font-size: 14px;
    font-weight: 500;
    border-radius: 0.375rem;
  }
  button.choice-button:hover:not(:disabled) {
    background-color: #ae82ef;
    color: white;
    border-color: #9c6ade;
  }
  button.choice-button.selected {
    background-color: #bfdbfe;
    color: #1e3a8a;
    border-color: #3b82f6;
  }
  button.choice-button.correct {
    background-color: #d1fae5;
    color: #065f46;
    border-color: #10b981;
  }
  button.choice-button.wrong {
    background-color: #fee2e2;
    color: #991b1b;
    border-color: #ef4444;
  }
  button.choice-button:disabled {
    cursor: not-allowed;
    opacity: 0.7;
  }

  button.submit-btn {
    margin-top: 12px;
    padding: 8px 16px;
    background-color: white;
    color: black;
    font-weight: 600;
    font-size: 0.875rem;
    border: 1px solid #ccc;
    border-radius: 0.375rem;
    cursor: pointer;
    transition: background-color 0.2s, border-color 0.2s;
  }
  button.submit-btn:hover:not(:disabled) {
    background-color: #f3f4f6;
    border-color: #a1a1aa;
  }
  button.submit-btn:disabled {
    background-color: #f9f9f9;
    color: #999;
    border-color: #ddd;
    cursor: not-allowed;
  }

  .feedback {
    margin-top: 12px;
    font-weight: bold;
  }
  .feedback.correct {
    color: #059669; /* green-600 */
  }
  .feedback.partial {
    color: #d97706; /* amber-600 */
  }
  .feedback.wrong {
    color: #b91c1c; /* red-700 */
  }

  .correct-answer {
    margin-top: 8px;
    color: #4b5563;
  }

  .explanation {
    margin-top: 8px;
    color: #6b7280;
    font-style: italic;
  }
</style>

<div class="choice-container">
  <div class="header">
    <CheckSquare class="w-5 h-5 text-primary" />
    多选题
  </div>

  <div class="question text-base font-semibold" style="color: var(--foreground); margin-bottom: 1rem;">
    {message.content.question}
  </div>

  {#each message.content.options as option, i}
    <button
      type="button"
      class="choice-button"
      class:selected={!submitted && selectedIndices.includes(i)}
      class:correct={submitted && message.content.answer.includes(i)}
      class:wrong={submitted && !message.content.answer.includes(i) && selectedIndices.includes(i)}
      on:click={() => toggleOption(i)}
      disabled={readOnly || submitted}
    >
      {option}
    </button>
  {/each}

  {#if !submitted}
    <button class="submit-btn" on:click={submit} disabled={selectedIndices.length === 0 || readOnly}>
      提交答案
    </button>
  {:else}
    <div class="feedback {feedbackClass}">{feedback}</div>

    {#if feedback.includes('不完全') || feedback.includes('完全不正确')}
      <div class="correct-answer">
        正确答案是：
        <strong>{message.content.answer.map(i => message.content.options[i]).join('，')}</strong>
      </div>
    {/if}

    {#if message.content.explanation}
      <div class="explanation">{message.content.explanation}</div>
    {/if}
  {/if}
</div>
