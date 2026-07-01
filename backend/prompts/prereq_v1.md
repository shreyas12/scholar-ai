You are mapping prerequisite relationships between concepts in a subject.

A prerequisite is a concept a learner must understand *first*. Only use concept
names from the provided list. Keep edges minimal and direct (don't chain
transitively — if A→B and B→C, don't also add A→C).

Return ONLY a JSON array of objects:
[{{"concept": "HNSW", "prerequisites": ["ANN", "Vector Search"]}}]

Omit concepts that have no prerequisites.

Concepts:
{concepts}

Prerequisites:
