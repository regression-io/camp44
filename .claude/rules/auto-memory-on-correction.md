# Auto-Memory on Correction Rule

## When You Are Corrected

**Immediately** create a memory or rule when:

1. **User corrects a factual error** (wrong domain, wrong path, wrong command, etc.)
   - Create a correction in `~/.claude/memory/corrections.md`
   - Or create a project-specific rule in `.claude/rules/`

2. **User provides new information you should remember** (API URLs, user preferences, project specifics)
   - Create appropriate memory entry

3. **User says "remember", "don't forget", "always/never do X"**
   - Create the appropriate memory type

## Examples of Corrections That Need Memory

- Wrong domain: "it's scalemate.regression.io not scalemate.me"
  → Create rule with correct domain
- Wrong command: "use npm run build not npm ci"
  → Create rule (already exists: no-npm-ci.md)
- Wrong user/account: "push with ruze00 not smartmem-dev"
  → Create rule (already exists: scalemate-git.md)

## How to Create

```bash
# For corrections
~/.claude/hooks/memory-write.sh correction "what was wrong" "what is correct" "context"

# For project-specific rules
Write a .md file in project/.claude/rules/
```

## Do Not Wait

Do not wait to be told to create a memory. If corrected, immediately:
1. Acknowledge the correction
2. Create the appropriate memory/rule
3. Continue with the task using the corrected information
