You are grading a learner's free-text answer as evidence of understanding.

Grade strictly against the reference material — reward demonstrated reasoning, not
keyword matching. A confident, fluent answer that is wrong or hollow scores low.

Concept: {concept}
Question: {question}
Reference material: {reference}
Learner's answer: {answer}

Return ONLY a JSON object:
{{
  "correct": true | false,
  "score": 0-100,
  "reasoning": "one sentence justifying the score",
  "misconception": "the specific wrong belief, or null"
}}
