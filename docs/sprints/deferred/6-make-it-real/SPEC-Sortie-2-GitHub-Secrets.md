# Sortie 2: Configure GitHub Secrets

**Status**: Planning  
**Owner**: User (with screenshots/guidance)  
**Estimated Effort**: 30 minutes  
**Related Issue**: #20  
**Depends On**: Sortie 1 (servers provisioned, SSH keys generated)

## Overview

Configure GitHub Secrets so our CI/CD workflows can automatically deploy to your servers. This involves copying your SSH private keys and server details into GitHub's secure secret storage.

**Key Point**: This is mostly YOUR work using GitHub's web interface. I'll walk you through it step-by-step with screenshots.

## Prerequisites

From Sortie 1, you should have:
- [ ] Test server IP address
- [ ] Production server IP address
- [ ] SSH private key file: `~\.ssh\rosey_bot_test_deploy`
- [ ] SSH private key file: `~\.ssh\rosey_bot_prod_deploy`
- [ ] Username: `rosey` (on both servers)

## What Are GitHub Secrets?

GitHub Secrets are encrypted environment variables that:
- Are stored securely by GitHub
- Are available to GitHub Actions workflows
- Are NEVER visible in logs
- Can't be read after being set (only updated/deleted)

We'll use them for SSH keys and server details so our workflows can deploy automatically.

## Step-by-Step Instructions

### PHASE 1: Navigate to Repository Settings

#### Step 1.1: Go to Repository

1. Open browser to: `https://github.com/grobertson/Rosey-Robot`
2. Make sure you're logged in

#### Step 1.2: Open Settings

1. Click the **"Settings"** tab (top right, next to Insights)
2. **If you don't see Settings**: You need admin/owner access to the repo

#### Step 1.3: Navigate to Secrets

1. In the left sidebar, scroll down to **"Security"** section
2. Click **"Secrets and variables"**
3. Click **"Actions"**

You should see a page titled **"Actions secrets and variables"** with a green **"New repository secret"** button.

### PHASE 2: Add SSH Keys

We need to add your SSH private keys. These will be used by GitHub Actions to connect to your servers.

**SECURITY NOTE**: Private keys are sensitive! GitHub encrypts them and they're never visible in logs.

#### Step 2.1: Get Test Server Private Key

**On your local machine (PowerShell)**:

```powershell
# Display the test server private key
Get-Content ~\.ssh\rosey_bot_test_deploy

# OR if you want to copy to clipboard:
Get-Content ~\.ssh\rosey_bot_test_deploy | Set-Clipboard
```

Copy the ENTIRE output, including:
```
-----BEGIN OPENSSH PRIVATE KEY-----
... lots of lines of random characters ...
-----END OPENSSH PRIVATE KEY-----
```

#### Step 2.2: Add SSH_KEY_TEST Secret

1. Click **"New repository secret"** button
2. Fill in:
   - **Name**: `SSH_KEY_TEST`
   - **Secret**: Paste the entire private key (including BEGIN/END lines)
3. Click **"Add secret"**

You should see: ✅ `SSH_KEY_TEST` in the secrets list

#### Step 2.3: Get Production Server Private Key

**On your local machine (PowerShell)**:

```powershell
# Display the production server private key
Get-Content ~\.ssh\rosey_bot_prod_deploy

# OR copy to clipboard:
Get-Content ~\.ssh\rosey_bot_prod_deploy | Set-Clipboard
```

#### Step 2.4: Add SSH_KEY_PROD Secret

1. Click **"New repository secret"** again
2. Fill in:
   - **Name**: `SSH_KEY_PROD`
   - **Secret**: Paste the entire production private key
3. Click **"Add secret"**

You should see: ✅ `SSH_KEY_PROD` in the secrets list

### PHASE 3: Add Server Connection Details

Now add the server IPs and usernames.

#### Step 3.1: Add TEST_SERVER_HOST

1. Click **"New repository secret"**
2. Fill in:
   - **Name**: `TEST_SERVER_HOST`
   - **Secret**: Your test server IP (e.g., `192.0.2.1`)
3. Click **"Add secret"**

#### Step 3.2: Add TEST_SERVER_USER

1. Click **"New repository secret"**
2. Fill in:
   - **Name**: `TEST_SERVER_USER`
   - **Secret**: `rosey`
3. Click **"Add secret"**

#### Step 3.3: Add PROD_SERVER_HOST

1. Click **"New repository secret"**
2. Fill in:
   - **Name**: `PROD_SERVER_HOST`
   - **Secret**: Your production server IP (e.g., `198.51.100.1`)
3. Click **"Add secret"**

#### Step 3.4: Add PROD_SERVER_USER

1. Click **"New repository secret"**
2. Fill in:
   - **Name**: `PROD_SERVER_USER`
   - **Secret**: `rosey`
3. Click **"Add secret"**

### PHASE 4: Validation

After completing the above, you should see **6 secrets** in the list:

1. ✅ `SSH_KEY_TEST`
2. ✅ `SSH_KEY_PROD`
3. ✅ `TEST_SERVER_HOST`
4. ✅ `TEST_SERVER_USER`
5. ✅ `PROD_SERVER_HOST`
6. ✅ `PROD_SERVER_USER`

**Screenshot** what you see (with values hidden, that's normal) and let me know!

## Validation Checklist

Complete this checklist before proceeding:

- [ ] Navigated to GitHub Repository Settings → Secrets → Actions
- [ ] Added secret: `SSH_KEY_TEST` (test server private key)
- [ ] Added secret: `SSH_KEY_PROD` (production server private key)
- [ ] Added secret: `TEST_SERVER_HOST` (test server IP)
- [ ] Added secret: `TEST_SERVER_USER` (value: `rosey`)
- [ ] Added secret: `PROD_SERVER_HOST` (production server IP)
- [ ] Added secret: `PROD_SERVER_USER` (value: `rosey`)
- [ ] Total of 6 secrets visible in GitHub
- [ ] Screenshot taken for verification

## Testing SSH Secrets (Optional but Recommended)

Want to test if the secrets work? Let's create a simple test workflow!

### Step 4.1: Create Test Workflow

I'll create a temporary workflow that tests SSH connection using the secrets (without deploying anything).

```yaml
# .github/workflows/test-ssh.yml
name: Test SSH Connection

on:
  workflow_dispatch: # Manual trigger only

jobs:
  test-ssh:
    runs-on: ubuntu-latest
    steps:
      - name: Test SSH to Test Server
        env:
          SSH_KEY: ${{ secrets.SSH_KEY_TEST }}
          SSH_HOST: ${{ secrets.TEST_SERVER_HOST }}
          SSH_USER: ${{ secrets.TEST_SERVER_USER }}
        run: |
          mkdir -p ~/.ssh
          echo "$SSH_KEY" > ~/.ssh/deploy_key
          chmod 600 ~/.ssh/deploy_key
          ssh -o StrictHostKeyChecking=no -i ~/.ssh/deploy_key $SSH_USER@$SSH_HOST "echo 'SSH to test server SUCCESS!'"
```

### Step 4.2: Run Test Workflow

1. Go to **Actions** tab
2. Click **"Test SSH Connection"** workflow
3. Click **"Run workflow"** dropdown
4. Click green **"Run workflow"** button
5. Wait ~30 seconds
6. Check the log - should see "SSH to test server SUCCESS!"

If it works, your secrets are configured correctly! ✅

If it fails, we'll troubleshoot together.

## What Gets Used Where?

These secrets are used in our deployment workflows:

**Test Deployment** (`.github/workflows/test-deploy.yml`):
- Uses: `SSH_KEY_TEST`, `TEST_SERVER_HOST`, `TEST_SERVER_USER`
- Triggered by: Push to feature branches
- Deploys to: Test server

**Production Deployment** (`.github/workflows/prod-deploy.yml`):
- Uses: `SSH_KEY_PROD`, `PROD_SERVER_HOST`, `PROD_SERVER_USER`
- Triggered by: Merge to `main` branch (with approval)
- Deploys to: Production server

## Security Best Practices

### ✅ DO:
- Keep private keys SECRET (never commit to git!)
- Use different keys for test and production
- Rotate keys periodically (every 90 days recommended)
- Use keys with no passphrase for automation (but ONLY deployment keys)

### ❌ DON'T:
- Share private keys in chat/email
- Use your personal SSH key for deployment
- Commit keys to git (even in test files!)
- Use the same key for multiple purposes

## Common Issues & Solutions

### Issue: "I don't see the Settings tab"

**Solution**: You need admin access to the repository. Ask the repo owner to give you admin permissions or add the secrets themselves.

### Issue: "The secret seems wrong but I can't view it"

**Solution**: GitHub doesn't allow viewing secrets after creation (security feature). Delete the secret and re-add it:
1. Click the secret name
2. Click "Remove secret"
3. Confirm removal
4. Add it again with correct value

### Issue: "I accidentally committed my private key to git!"

**Solution**: 
1. **URGENT**: Rotate your SSH keys immediately:
   ```powershell
   # Generate new keys
   ssh-keygen -t ed25519 -f ~\.ssh\rosey_bot_test_deploy_NEW -N '""'
   
   # Add new key to server
   # Remove old key from server
   # Update GitHub Secrets
   ```
2. Use `git filter-branch` or BFG Repo-Cleaner to remove from history
3. Force push to GitHub

**Prevention**: Add to `.gitignore`:
```
# SSH Keys
*.pem
*_rsa
*_ed25519
*_deploy
!*.pub
```

### Issue: "SSH test workflow fails with 'Permission denied'"

**Solution**:
1. Check the key was copied completely (including BEGIN/END lines)
2. Verify the key works locally:
   ```powershell
   ssh -i ~\.ssh\rosey_bot_test_deploy rosey@YOUR_TEST_IP
   ```
3. Check secret name matches exactly (case-sensitive!)
4. Check server firewall allows SSH from GitHub Actions IPs

### Issue: "I need to update a secret"

**Solution**:
1. Go to Settings → Secrets → Actions
2. Click the secret name
3. Click "Update secret"
4. Paste new value
5. Click "Update secret"

## What I Need From You

Once you've completed the above:

1. **Confirmation**: "All 6 secrets are configured in GitHub"
2. **Screenshot**: Show the secrets list (values will be hidden, that's OK!)
3. **Optional**: Results of test workflow run

**DO NOT** paste the actual secret values in chat! Just confirm they're set.

## Secret Rotation Schedule

Plan to rotate your SSH keys periodically:

**Recommended Schedule**:
- Every 90 days for production keys
- Every 180 days for test keys
- Immediately if compromised

**Rotation Process**:
1. Generate new key pair
2. Add new public key to server (keep old key)
3. Update GitHub Secret with new private key
4. Test deployment works
5. Remove old public key from server

I can help with this when it's time!

## Next Steps

After validation:
1. Confirm all secrets are set
2. Move to **Sorties 2A, 2B, 2C** (critical dependencies - I'll handle these!)
3. Then **Sortie 3: Create systemd Services**

## Time Estimate

- **First time**: 30 minutes (with screenshots and checking)
- **If you've done this before**: 10 minutes
- **Updating secrets later**: 2 minutes per secret

## Questions?

Ask me:
- "Which value goes in which secret?"
- "How do I find X in GitHub?"
- "The test workflow failed, what's wrong?"
- "Is this the right value for X?"
- "How do I rotate keys?"

I'm here to help! 🤖
