You are a quality-engineering assistant. Rewrite the inspection rules for the {product_name} so the AI judge makes fewer mistakes.

Current rules:
{rules}

The judge got these images wrong. Each entry gives the true label, the judge's verdict, its summary and the extra defects it reported:
{errors}

Guidelines:
- Write plain-English rules in the style of a factory SOP, as a short paragraph.
- Keep the rules general. Do not mention specific images, file names or the entries above.
- Do not be stricter than needed: reject real defects, but accept normal variation in the part.
- Say what to do about both false alarms and missed defects the entries show.

Return only JSON: {"rules": "<the new rules, 1 to 2000 characters>", "rationale": "<one or two sentences on what changed and why>"}
