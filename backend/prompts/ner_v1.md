Extract the named technical entities from the passage.

Return ONLY a JSON object with these keys (each a list of short names, omit empties):
{{
  "algorithms": [],
  "libraries": [],
  "frameworks": [],
  "companies": [],
  "datasets": [],
  "metrics": [],
  "authors": []
}}

Only include entities that actually appear in the passage. No prose.

Passage:
{chunk}

Entities:
