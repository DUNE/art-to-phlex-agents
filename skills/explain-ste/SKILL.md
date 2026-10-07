---
name: explain-ste
description: Rewrite or write text in ASD-STE100 (Simplified Technical English) style. Use when the user asks for STE, "simplified technical English", or plain unambiguous wording for procedures, runbooks, install guides, onboarding docs, warnings, or text for non-native English readers or translation. Do not apply unless asked or the text is clearly a procedure meant for that audience.
---

# ASD-STE100 style

Write the text the user names. Do not change how you write the rest of the conversation.

## Rules to follow

- Procedure sentences: 20 words or fewer. Descriptive sentences: 25 words or fewer.
- One idea per sentence. One topic per paragraph. Paragraphs of 6 sentences or fewer.
- Use the active voice and the present tense. Name who or what does the action.
- Use the imperative for steps ("Set the variable."). Put one action in each step.
- Put warnings and cautions before the step they apply to. Use "must" or "do not".
- Use one word for one meaning. Do not swap synonyms for variety.
- Avoid idioms and phrasal verbs ("fall back to", "set up"). Use a plain verb ("use", "configure").
- Keep technical names exactly as written (`tmux`, `status-right`, file paths, commands).
- Use "the" and "a" in full. Do not drop articles.
- Use a list for 3 or more parallel items.

## Limits

The official STE dictionary has about 900 approved words, each with one approved meaning. You cannot check every word against it. Tell the user the result is "STE-style" and not certified, unless they give you a checker.

## Output

Return the rewritten text. Add a short note only for terms you could not simplify. Do not include a "what changed" list unless asked. Follow the user's rule on no em-dashes.
