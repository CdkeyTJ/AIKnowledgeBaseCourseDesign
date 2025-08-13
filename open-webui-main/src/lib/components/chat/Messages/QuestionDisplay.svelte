<script>
	export let message; // 接收后端返回的题目数组

	let questions = message.content.questions;
	import ChoiceQuestionMessage from './ChoiceQuestionMessage.svelte';
	import TrueFalseQuestionMessage from './TrueFalseQuestionMessage.svelte';
	import MultipleChoiceQuestionMessage from './MultipleChoiceQuestionMessage.svelte';
</script>

<div class="questions-container">
	{#each questions as message, index}
		<div class="question-item">
			{#if message.type === 'choice_question'}
				<ChoiceQuestionMessage {message} />
			{:else if message.type === 'true_false_question'}
				<TrueFalseQuestionMessage {message} />
			{:else if message.type === 'multiple_choice_question'}
				<MultipleChoiceQuestionMessage {message} />
			{/if}
		</div>
	{/each}
</div>

<style>
	.questions-container {
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}
	.question-item {
		padding: 1rem;
		/* border: 1px solid #ddd; */
		border-radius: 8px;
		/* background-color: #f9f9f9; */
	}
</style>
