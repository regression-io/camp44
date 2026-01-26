# CI/CD Verification Rule

## After Every Push

After pushing changes to a repository with CI/CD workflows, ALWAYS:

1. **Wait briefly** (5-10 seconds) for the workflow to start
2. **Check workflow status** using `gh run list --repo <owner/repo> --limit 3`
3. **If any run is failing**, investigate with:
   - `gh run view <run-id> --log-failed` to see failure details
   - Fix the issue before moving on to other tasks
4. **Verify deployment** if there's a deploy workflow:
   - Check health endpoints
   - Confirm the new changes are live

## Common CI/CD Issues

- Missing secrets (HETZNER_SSH_KEY, GH_PAT, etc.)
- Workflow file syntax errors (commented triggers, invalid YAML)
- Dependency installation failures
- Test failures

## Commands Reference

```bash
# List recent runs
gh run list --repo owner/repo --limit 5

# View failed run logs
gh run view <run-id> --repo owner/repo --log-failed

# View specific workflow runs
gh run list --repo owner/repo --workflow=deploy.yml

# Re-run a failed workflow
gh run rerun <run-id> --repo owner/repo
```
