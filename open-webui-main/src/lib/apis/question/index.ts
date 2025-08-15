// @CDK:建立前端接口连接后端/api/generate-question
import { WEBUI_BASE_URL } from '$lib/constants';

export const generateQuestion = async (
	token: string = '',
	prompt: string,
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

	// return {
	// 	questions: {
	// 		type: 'question',
	// 		questions: [
	// 			  {
	// 				"type": "choice_question",
	// 				"question": "在Python中，用于处理日期和时间的标准库是哪一个？",
	// 				"options": ["random", "datetime", "time", "date"],
	// 				"answer": 1,
	// 				"explanation": "正确答案是 datetime 库。其他选项分别是 random（用于生成随机数）、time（主要用于处理当前时间）和 date（处理日期部分）库。"
	// 			  },
	// 			  {
	// 				"type": "true_false_question",
	// 				"question": "伽罗瓦是美国数学家",
	// 				"answer": false,
	// 				"explanation": "伽罗瓦是法国天才数学家，但他英年早逝。"
	// 			  },
	// 			  {
	// 				"type": "multiple_choice_question",
	// 				"question": "请选择0，2，3",
	// 				"options": ['磷脂', 'DNA', '胆固醇', '蛋白质', '葡萄糖'],
	// 				"answer": [0, 2, 3],
	// 				"explanation": "future0"
	// 			  }
	// 			]
	// 		}
	// 	};
	// };
