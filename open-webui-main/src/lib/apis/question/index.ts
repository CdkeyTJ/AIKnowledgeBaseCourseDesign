// @CDK:建立前端接口连接后端/api/generate-question
import { WEBUI_BASE_URL } from '$lib/constants';

export const generateQuestion = async (
	token: string = '',
	prompt: string,
    files: [],
	kbId: string | null = null,  // 新增知识库ID参数
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
            files: files,
			kb_id: kbId  // 传递知识库ID到后端
		})
	})
		.then(async (res) => {
			console.log(res)
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
