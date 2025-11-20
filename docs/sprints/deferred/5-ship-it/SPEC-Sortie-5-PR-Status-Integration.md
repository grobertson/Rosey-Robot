# SPEC: Sortie 5 - PR Status Integration

**Sprint:** 5 (ship-it)  
**Sortie:** 5 of 12  
**Status:** Ready for Implementation  
**Depends On:** Sortie 4 (Test Deploy Workflow)

---

## Objective

Add automated PR comments with deployment status, test channel URL, workflow logs, and deployment metadata. This provides stakeholders with immediate visibility into test deployments without navigating GitHub Actions.

## Success Criteria

- ✅ Bot comments on PR after test deployment completes
- ✅ Comment includes deployment status (success/failure)
- ✅ Test channel URL included for easy access
- ✅ Link to workflow run logs
- ✅ Deployment timestamp and metadata
- ✅ Comment updates on subsequent deployments (edit vs new comment)
- ✅ Clear, readable formatting with emojis

## Technical Specification

### GitHub API Integration

**Method:** Use `actions/github-script` action for PR comments

**Permissions Required:**
```yaml
permissions:
  pull-requests: write
  contents: read
```

**API Endpoints Used:**
- `github.rest.issues.listComments` - Find existing bot comments
- `github.rest.issues.createComment` - Create new comment
- `github.rest.issues.updateComment` - Update existing comment

### Comment Format

#### Success Comment

```markdown
## 🚀 Test Deployment Successful

Your changes have been deployed to the test channel!

**🔗 Test Channel:** https://cytu.be/r/test-rosey  
**⏱️ Deployed:** 2024-11-12 15:30:45 UTC  
**📦 Commit:** abc1234 (feat: add new feature)  
**🔍 Workflow:** [View logs](https://github.com/org/repo/actions/runs/123456)

**✅ Checks Passed:**
- ✓ Linting (ruff, mypy)
- ✓ Tests (567 tests, 92% coverage)
- ✓ Deployment (health check passed)

---

<details>
<summary>Deployment Details</summary>

- **Environment:** test
- **Bot Version:** main@abc1234
- **Database:** test-rosey.db
- **Start Time:** 15:30:40 UTC
- **End Time:** 15:30:45 UTC
- **Duration:** 5 seconds

</details>

<sub>🤖 Automated deployment via GitHub Actions</sub>
```

#### Failure Comment

```markdown
## ❌ Test Deployment Failed

The test deployment encountered an error.

**⏱️ Failed at:** 2024-11-12 15:30:45 UTC  
**📦 Commit:** abc1234 (feat: add new feature)  
**🔍 Workflow:** [View logs](https://github.com/org/repo/actions/runs/123456)

**Error:** Health check failed after deployment

**Checks:**
- ✓ Linting passed
- ✓ Tests passed
- ❌ Deployment failed

**Next Steps:**
1. Review the [workflow logs](https://github.com/org/repo/actions/runs/123456)
2. Check the error message above
3. Fix the issue and push a new commit
4. The deployment will automatically retry

---

<sub>🤖 Automated deployment via GitHub Actions</sub>
```

### Comment Management Strategy

**Approach:** Update existing comment vs create new

**Logic:**
1. Search for existing bot comment on PR
2. If found: Update the existing comment (avoid spam)
3. If not found: Create new comment
4. Use HTML comment marker to identify bot comments

**Marker:**
```html
<!-- rosey-bot-deployment-status -->
```

### Deployment Metadata

**Information to Include:**

Required:
- Deployment status (success/failure)
- Test channel URL
- Deployment timestamp
- Commit SHA and message
- Workflow run link

Optional:
- Deployment duration
- Bot version
- Database name
- Health check details
- Error message (on failure)

**Data Sources:**
- `github.context` - PR, commit, workflow info
- `github.sha` - Commit SHA
- Workflow outputs - Deployment time, status
- Environment variables - Configured values

## Implementation

### Update .github/workflows/test-deploy.yml

Add PR comment job after deployment:

```yaml
  comment-status:
    name: Comment Deployment Status
    needs: [deploy-test]
    runs-on: ubuntu-latest
    if: always()  # Run even if deployment fails
    permissions:
      pull-requests: write
      contents: read
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Comment on PR - Success
        if: needs.deploy-test.result == 'success'
        uses: actions/github-script@v7
        with:
          script: |
            const marker = '<!-- rosey-bot-deployment-status -->';
            const deployTime = new Date().toISOString();
            const commitSha = context.sha.substring(0, 7);
            const workflowUrl = `${context.serverUrl}/${context.repo.owner}/${context.repo.repo}/actions/runs/${context.runId}`;
            
            const body = `${marker}
            ## 🚀 Test Deployment Successful
            
            Your changes have been deployed to the test channel!
            
            **🔗 Test Channel:** https://cytu.be/r/test-rosey  
            **⏱️ Deployed:** ${deployTime}  
            **📦 Commit:** ${commitSha}  
            **🔍 Workflow:** [View logs](${workflowUrl})
            
            **✅ Checks Passed:**
            - ✓ Linting (ruff, mypy)
            - ✓ Tests (567 tests, 92% coverage)
            - ✓ Deployment (health check passed)
            
            ---
            
            <details>
            <summary>Deployment Details</summary>
            
            - **Environment:** test
            - **Bot Version:** main@${commitSha}
            - **Database:** test-rosey.db
            - **Deployed at:** ${deployTime}
            
            </details>
            
            <sub>🤖 Automated deployment via GitHub Actions</sub>
            `.trim();
            
            // Find existing comment
            const { data: comments } = await github.rest.issues.listComments({
              owner: context.repo.owner,
              repo: context.repo.repo,
              issue_number: context.issue.number,
            });
            
            const botComment = comments.find(comment => 
              comment.body.includes(marker)
            );
            
            if (botComment) {
              // Update existing comment
              await github.rest.issues.updateComment({
                owner: context.repo.owner,
                repo: context.repo.repo,
                comment_id: botComment.id,
                body: body
              });
            } else {
              // Create new comment
              await github.rest.issues.createComment({
                owner: context.repo.owner,
                repo: context.repo.repo,
                issue_number: context.issue.number,
                body: body
              });
            }
      
      - name: Comment on PR - Failure
        if: needs.deploy-test.result == 'failure'
        uses: actions/github-script@v7
        with:
          script: |
            const marker = '<!-- rosey-bot-deployment-status -->';
            const deployTime = new Date().toISOString();
            const commitSha = context.sha.substring(0, 7);
            const workflowUrl = `${context.serverUrl}/${context.repo.owner}/${context.repo.repo}/actions/runs/${context.runId}`;
            
            const body = `${marker}
            ## ❌ Test Deployment Failed
            
            The test deployment encountered an error.
            
            **⏱️ Failed at:** ${deployTime}  
            **📦 Commit:** ${commitSha}  
            **🔍 Workflow:** [View logs](${workflowUrl})
            
            **Checks:**
            - ✓ Linting passed
            - ✓ Tests passed
            - ❌ Deployment failed
            
            **Next Steps:**
            1. Review the [workflow logs](${workflowUrl})
            2. Check the error message in the logs
            3. Fix the issue and push a new commit
            4. The deployment will automatically retry
            
            ---
            
            <sub>🤖 Automated deployment via GitHub Actions</sub>
            `.trim();
            
            // Find existing comment
            const { data: comments } = await github.rest.issues.listComments({
              owner: context.repo.owner,
              repo: context.repo.repo,
              issue_number: context.issue.number,
            });
            
            const botComment = comments.find(comment => 
              comment.body.includes(marker)
            );
            
            if (botComment) {
              // Update existing comment
              await github.rest.issues.updateComment({
                owner: context.repo.owner,
                repo: context.repo.repo,
                comment_id: botComment.id,
                body: body
              });
            } else {
              // Create new comment
              await github.rest.issues.createComment({
                owner: context.repo.owner,
                repo: context.repo.repo,
                issue_number: context.issue.number,
                body: body
              });
            }
```

### Alternative: Separate Script File

For cleaner workflow, create `scripts/comment-pr-status.js`:

```javascript
#!/usr/bin/env node
/**
 * Post deployment status comment to PR
 * Usage: node scripts/comment-pr-status.js <success|failure>
 */

const MARKER = '<!-- rosey-bot-deployment-status -->';

async function main({ github, context, core }, status) {
  const deployTime = new Date().toISOString();
  const commitSha = context.sha.substring(0, 7);
  const workflowUrl = `${context.serverUrl}/${context.repo.owner}/${context.repo.repo}/actions/runs/${context.runId}`;
  
  let body;
  
  if (status === 'success') {
    body = `${MARKER}
## 🚀 Test Deployment Successful

Your changes have been deployed to the test channel!

**🔗 Test Channel:** https://cytu.be/r/test-rosey  
**⏱️ Deployed:** ${deployTime}  
**📦 Commit:** ${commitSha}  
**🔍 Workflow:** [View logs](${workflowUrl})

**✅ Checks Passed:**
- ✓ Linting (ruff, mypy)
- ✓ Tests (567 tests, 92% coverage)
- ✓ Deployment (health check passed)

---

<details>
<summary>Deployment Details</summary>

- **Environment:** test
- **Bot Version:** main@${commitSha}
- **Database:** test-rosey.db
- **Deployed at:** ${deployTime}

</details>

<sub>🤖 Automated deployment via GitHub Actions</sub>
`.trim();
  } else {
    body = `${MARKER}
## ❌ Test Deployment Failed

The test deployment encountered an error.

**⏱️ Failed at:** ${deployTime}  
**📦 Commit:** ${commitSha}  
**🔍 Workflow:** [View logs](${workflowUrl})

**Checks:**
- ✓ Linting passed
- ✓ Tests passed
- ❌ Deployment failed

**Next Steps:**
1. Review the [workflow logs](${workflowUrl})
2. Check the error message in the logs
3. Fix the issue and push a new commit
4. The deployment will automatically retry

---

<sub>🤖 Automated deployment via GitHub Actions</sub>
`.trim();
  }
  
  // Find existing comment
  const { data: comments } = await github.rest.issues.listComments({
    owner: context.repo.owner,
    repo: context.repo.repo,
    issue_number: context.issue.number,
  });
  
  const botComment = comments.find(comment => 
    comment.body.includes(MARKER)
  );
  
  if (botComment) {
    core.info(`Updating existing comment ${botComment.id}`);
    await github.rest.issues.updateComment({
      owner: context.repo.owner,
      repo: context.repo.repo,
      comment_id: botComment.id,
      body: body
    });
  } else {
    core.info('Creating new comment');
    await github.rest.issues.createComment({
      owner: context.repo.owner,
      repo: context.repo.repo,
      issue_number: context.issue.number,
      body: body
    });
  }
  
  core.info('Comment posted successfully');
}

module.exports = main;
```

Then use in workflow:

```yaml
- name: Comment on PR
  uses: actions/github-script@v7
  with:
    script: |
      const commentScript = require('./scripts/comment-pr-status.js');
      await commentScript({ github, context, core }, '${{ needs.deploy-test.result }}');
```

## Implementation Steps

### Step 1: Add Permissions to Workflow

Update `.github/workflows/test-deploy.yml`:

```yaml
name: Test Deployment

on:
  pull_request:
    types: [opened, synchronize, reopened]
    branches: [main]

permissions:
  contents: read
  pull-requests: write  # Add this

jobs:
  # ... existing jobs ...
```

### Step 2: Add Comment Job

Add the `comment-status` job after `deploy-test` job in workflow.

### Step 3: Test Comment Creation

1. Create test PR
2. Wait for deployment to complete
3. Check PR for bot comment
4. Verify format and links

### Step 4: Test Comment Update

1. Push new commit to same PR
2. Wait for deployment
3. Verify existing comment updated (not new comment created)

### Step 5: Test Failure Comment

1. Create PR with deployment failure
2. Verify failure comment appears
3. Check error messaging is clear

## Validation Checklist

- [ ] Workflow has `pull-requests: write` permission
- [ ] Comment job added after deployment
- [ ] Success comment includes all required fields
- [ ] Failure comment includes all required fields
- [ ] Test channel URL correct
- [ ] Workflow run link works
- [ ] Timestamp formatted correctly
- [ ] Existing comments updated (not duplicated)
- [ ] HTML marker present in comments
- [ ] Emojis render correctly
- [ ] Markdown formatting clean
- [ ] Collapsible details work

## Testing Strategy

### Test 1: First Deployment (Success)

**Steps:**
1. Create new PR
2. Wait for successful deployment
3. Check PR comments

**Expected:**
- New comment created
- All fields populated
- Links work
- Format clean

### Test 2: Subsequent Deployment (Success)

**Steps:**
1. Push new commit to existing PR
2. Wait for deployment
3. Check PR comments

**Expected:**
- Existing comment updated
- No new comment created
- Timestamp updated
- Commit SHA updated

### Test 3: Deployment Failure

**Steps:**
1. Create PR with failing deployment
2. Wait for failure
3. Check PR comments

**Expected:**
- Failure comment posted
- Error information clear
- Next steps provided
- Links to logs work

### Test 4: Transition from Failure to Success

**Steps:**
1. Start with failing deployment
2. Fix issue and push
3. Wait for successful deployment
4. Check comment updated

**Expected:**
- Comment changes from failure to success
- Old failure message replaced
- Success status shown

### Test 5: Multiple PRs Concurrent

**Steps:**
1. Create 2 PRs simultaneously
2. Wait for both deployments
3. Check each PR has its own comment

**Expected:**
- Each PR has separate comment
- No cross-contamination
- Both comments correct

## Comment Template Variations

### Minimal (MVP)

```markdown
<!-- rosey-bot-deployment-status -->
## ✅ Deployed to Test

Test channel: https://cytu.be/r/test-rosey  
[View logs](workflow-url)
```

### Standard (Recommended)

```markdown
<!-- rosey-bot-deployment-status -->
## 🚀 Test Deployment Successful

**Test Channel:** https://cytu.be/r/test-rosey  
**Deployed:** timestamp  
**Commit:** sha  
**Logs:** [link](url)

✅ All checks passed
```

### Detailed (Full)

```markdown
<!-- rosey-bot-deployment-status -->
## 🚀 Test Deployment Successful

**🔗 Test Channel:** https://cytu.be/r/test-rosey  
**⏱️ Deployed:** timestamp  
**📦 Commit:** sha (message)  
**🔍 Workflow:** [View logs](url)

**Checks:**
- ✓ Linting passed
- ✓ Tests passed (567 tests, 92% coverage)
- ✓ Deployment successful

<details>
<summary>Deployment Details</summary>

Full metadata here

</details>
```

## Performance Impact

**Comment API Calls:**
- List comments: ~200ms
- Create/update comment: ~300ms
- **Total:** < 1 second additional time

**Workflow Duration:**
- Comment job runs in parallel after deployment
- No impact on deployment time
- Total workflow time: +0-10 seconds

## Security Considerations

### Permissions

**Required:**
- `pull-requests: write` - To create/update comments
- `contents: read` - To read workflow context

**Not Required:**
- `actions: write` - Not needed
- `checks: write` - Not needed

### Information Disclosure

**Safe to Include:**
- Public repository information
- Commit SHAs
- Timestamps
- Workflow URLs
- Test channel URL (public)

**Never Include:**
- Passwords or secrets
- Private configuration values
- Database credentials
- API tokens

### XSS Protection

GitHub automatically sanitizes markdown comments, but still:
- ✅ Use markdown formatting only
- ✅ Validate user input if included
- ❌ Don't inject raw HTML
- ❌ Don't use user content without escaping

## Troubleshooting

### Comment Not Appearing

**Possible Causes:**
1. Missing `pull-requests: write` permission
2. Not a pull request event
3. Comment job didn't run
4. API rate limit reached

**Solutions:**
1. Add permission to workflow
2. Verify trigger is `pull_request`
3. Check workflow logs
4. Wait and retry

### Comment Duplicated

**Possible Causes:**
1. Marker not found in existing comment
2. Multiple jobs running simultaneously
3. Marker HTML comment malformed

**Solutions:**
1. Verify marker string exact
2. Use `needs:` to sequence jobs
3. Check HTML comment syntax

### Links Not Working

**Possible Causes:**
1. Context variables incorrect
2. URL construction error
3. Repository private (workflow logs)

**Solutions:**
1. Verify `context.repo.owner`, etc.
2. Test URL construction
3. Check repository visibility

## Future Enhancements

### Phase 1 Additions:
- Include deployment duration
- Add bot response time metrics
- Show database size

### Phase 2 Additions:
- Screenshot of test channel
- Comparison with previous deployment
- Link to diff view

### Phase 3 Additions:
- Slack/Discord notifications
- Email notifications
- Custom webhook notifications

## Commit Message

```bash
git add .github/workflows/test-deploy.yml
git commit -m "feat: add PR status comments for test deployments

Enhanced test deployment workflow with automated PR comments.

.github/workflows/test-deploy.yml:
- Added comment-status job after deployment
- Runs on both success and failure
- Updates existing comments (avoids spam)
- Includes deployment metadata

Comment Features:
- Test channel URL for easy access
- Deployment timestamp
- Commit SHA and workflow link
- Success/failure status with checks
- Collapsible deployment details
- Clear next steps on failure

Comment Management:
- HTML marker for bot comment identification
- Updates existing comment on new deployments
- Separate success/failure templates
- Clean markdown formatting with emojis

Permissions:
- Added pull-requests: write permission
- Secure handling of workflow context
- No secrets exposed in comments

Benefits:
- Stakeholders don't need to navigate GitHub Actions
- Immediate visibility into deployment status
- Easy access to test channel and logs
- Professional, branded comments

This provides stakeholders with immediate feedback on test
deployments directly in the PR conversation.

SPEC: Sortie 5 - PR Status Integration"
```

## Related Documentation

- **Sortie 4:** Test Deploy Workflow (base workflow)
- **GitHub Actions:** actions/github-script documentation
- **GitHub API:** Issues/Comments API reference

## Next Sortie

**Sortie 6: Test Channel Verification** - Add post-deployment verification steps including connection tests and basic command validation.

---

**Implementation Time Estimate:** 2-3 hours  
**Risk Level:** Low  
**Priority:** High (stakeholder visibility)  
**Dependencies:** Sortie 4 complete
