// @CDK:建立前端接口连接后端/api/generate-question
import { WEBUI_BASE_URL } from '$lib/constants';

export const generateQuestion = async (
	token: string = '',
	prompt: string,
	subject: string = '数学',
	difficulty: string = '简单'
) => {
	let error = null;

	const res = await fetch(`${WEBUI_BASE_URL}/api/generate-question`, {
		method: 'POST',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			...(token && { Authorization: `Bearer ${token}` })
		},
		body: JSON.stringify({
			prompt: prompt,
			subject: subject,
			difficulty: difficulty
		})
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			console.error(err);
			if ('detail' in err) {
				error = err.detail;
			}
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};
