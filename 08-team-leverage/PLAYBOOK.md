# Making yourself unnecessary on purpose

The role is judged by how many questions *stop arriving*. A repeatable loop:

1. **Log it.** Every request goes in `request_log.csv` (date, requester, category, minutes). It takes ten seconds.
2. **Rank it weekly.** `python -m team_leverage.requests_log request_log.csv` ranks categories by total minutes and says what fix each deserves.
3. **Match the fix to the pattern.**
   - asked twice: add to an FAQ
   - asked three or more times: a how-to with a copy-paste example
   - asked five or more times by several people: a tool or a slash command (see `.claude/commands/`)
4. **Teach the method, not the answer.** Reply with how to check it, then link the command or doc. "Why didn't Maria get access?" becomes `/trace-customer`.
5. **Close the loop.** If a category stays near the top after you shipped a fix, the fix is wrong. Ask the people asking.

## For colleagues whose "coding language is English"
- Give them commands that explain themselves (`/explain-simply`) and end every answer with how to verify it.
- Make dangerous things read-only by default (the tools here recommend; a person applies).
- Put the five most common questions in the repo's `CLAUDE.md` so their own Claude session already knows the rules.

## What to measure
Asks per week in the top category, median minutes per ask, and share of questions that resolved without you. If the first two are not falling, you are acting as a help desk.
