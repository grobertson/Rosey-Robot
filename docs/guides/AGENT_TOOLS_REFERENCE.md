# Agent Tools Reference

**Project:** Rosey-Robot  
**Last Updated:** November 21, 2025  

This guide catalogs all tools and Model Context Protocol (MCP) servers available to GitHub Copilot agents in the Rosey-Robot project.

---

## Table of Contents

1. [GitHub Copilot Built-in Tools](#github-copilot-built-in-tools)
2. [GitHub MCP Server](#github-mcp-server)
3. [Hugging Face MCP Server](#hugging-face-mcp-server)
4. [Web/Documentation MCP](#webdocumentation-mcp)
5. [AI Development Toolkit](#ai-development-toolkit)
6. [Command Line Tools](#command-line-tools)
7. [Tool Selection Strategy](#tool-selection-strategy)
8. [Best Practices](#best-practices)

---

## GitHub Copilot Built-in Tools

### File Operations

#### read_file
Read file contents with optional line ranges for large files.

**Parameters**:
- `filePath` (required): Absolute path to file
- `offset` (optional): Starting line number (1-indexed)
- `limit` (optional): Maximum lines to read

**Example**:
```markdown
Prompt: "Read lib/bot.py lines 100-200 to understand the connection logic"
```

#### create_file
Create new files with content. Creates parent directories automatically.

**Parameters**:
- `filePath` (required): Absolute path for new file
- `content` (required): File contents

**Example**:
```markdown
Prompt: "Create tests/unit/test_new_feature.py with basic test structure"
```

#### replace_string_in_file
Edit existing files by replacing exact string matches. Requires 3-5 lines of context before/after.

**Parameters**:
- `filePath` (required): Absolute path to file
- `oldString` (required): Exact text to replace (with context)
- `newString` (required): Replacement text

**Example**:
```markdown
Prompt: "In lib/bot.py, update the _handle_message method to log timestamps"
```

#### multi_replace_string_in_file
Batch edit multiple files efficiently in a single operation.

**Parameters**:
- `replacements` (required): Array of replacement operations
- `explanation` (required): Description of changes

**Example**:
```markdown
Prompt: "Update all test files to use the new fixture pattern"
```

**Best Practice**: Use this for multiple edits to avoid sequential operations.

#### list_dir
List contents of a directory.

**Parameters**:
- `path` (required): Absolute directory path

**Returns**: Names ending in `/` are folders, others are files.

#### file_search
Search for files by glob pattern from workspace root.

**Parameters**:
- `query` (required): Glob pattern (e.g., `**/*.py`, `tests/**/test_*.py`)
- `maxResults` (optional): Limit results

**Example**:
```markdown
Prompt: "Find all Python files in the tests directory"
```

#### grep_search
Fast text search across workspace (exact string or regex).

**Parameters**:
- `query` (required): Search pattern
- `isRegexp` (required): Boolean for regex mode
- `includePattern` (optional): Glob for files to search
- `maxResults` (optional): Limit results

**Example**:
```markdown
Prompt: "Search for all uses of 'async def' in lib/ directory"
```

**Tip**: Use alternation (`function|method|procedure`) to search multiple terms at once.

#### semantic_search
Natural language code search across workspace.

**Parameters**:
- `query` (required): Semantic search description

**Example**:
```markdown
Prompt: "Find code that handles database connections"
```

**Best For**: Conceptual searches when exact terms are unknown.

---

### Code Intelligence

#### list_code_usages
Find all references, definitions, and implementations of symbols.

**Parameters**:
- `symbolName` (required): Function, class, method, or variable name
- `filePaths` (optional): Files likely containing definition

**Example**:
```markdown
Prompt: "Find all places where the send_chat method is called"
```

**Use Cases**:
- Find sample implementations of interfaces
- Check how functions are used across codebase
- Update all usages when changing signatures

#### get_errors
Get compile/lint errors from VS Code diagnostics.

**Parameters**:
- `filePaths` (optional): Specific files to check, or omit for all errors

**Example**:
```markdown
Prompt: "Check for any errors in the recently modified files"
```

**Best Practice**: Call after file edits to validate changes.

#### get_vscode_api
Get VS Code extension API documentation.

**Parameters**:
- `query` (required): Specific API/interface/concept

**Use**: VS Code extension development only.

---

### Testing & Execution

#### runTests
Execute unit tests with coverage reporting.

**Parameters**:
- `files` (optional): Absolute paths to test files
- `testNames` (optional): Specific test names
- `mode` (optional): `run` (default) or `coverage`
- `coverageFiles` (optional): Files for detailed coverage

**Example**:
```markdown
Prompt: "Run all NATS integration tests with coverage"
```

**Best Practice**: Preferred over terminal pytest commands.

#### run_in_terminal
Execute PowerShell commands in persistent terminal.

**Parameters**:
- `command` (required): PowerShell command
- `explanation` (required): Description for user
- `isBackground` (required): Boolean for background processes

**Example**:
```markdown
Prompt: "Install the new dependencies from requirements.txt"
```

**Windows Tips**:
- Use `;` to chain commands (never `&&`)
- Use absolute paths to avoid navigation issues
- Prefer PowerShell cmdlets over aliases

#### get_terminal_output
Retrieve output from background terminal process.

**Parameters**:
- `id` (required): Terminal ID from run_in_terminal

#### terminal_last_command
Get the last command run in active terminal.

#### run_notebook_cell
Execute Jupyter notebook cells.

**Parameters**:
- `filePath` (required): Notebook path
- `cellId` (required): Cell ID to execute
- `continueOnError` (optional): Boolean

**Note**: Do not execute Markdown cells.

---

### Python Development

#### configure_python_environment
Set up Python virtual environment for workspace.

**Parameters**:
- `resourcePath` (optional): Path to Python file/workspace

**Best Practice**: Always call before Python operations.

#### get_python_environment_details
Get environment info (type, version, packages).

**Parameters**:
- `resourcePath` (optional): Path to Python file/workspace

**Returns**: Environment type (conda, venv), Python version, installed packages.

#### get_python_executable_details
Get Python executable path and command construction details.

**Parameters**:
- `resourcePath` (optional): Path to Python file/workspace

**Use**: For constructing fully qualified Python commands in terminal.

#### install_python_packages
Install packages via pip in configured environment.

**Parameters**:
- `packageList` (required): Array of package names
- `resourcePath` (optional): Path to Python file/workspace

**Example**:
```markdown
Prompt: "Install pytest, pytest-cov, and pytest-asyncio"
```

---

### Project Setup

#### create_new_workspace
Scaffold complete project structures.

**Parameters**:
- `query` (required): Description of workspace to create

**Use**: Full project initialization (TypeScript, React, Node.js, MCP servers, VS Code extensions).

**When NOT to use**: Individual files, simple additions to existing projects.

#### get_project_setup_info
Get setup steps for specific project types.

**Parameters**:
- `projectType` (required): `python-script`, `python-project`, `mcp-server`, `vscode-extension`, `next-js`, `vite`, `other`

**Use**: After create_new_workspace for detailed setup guidance.

#### create_and_run_task
Create VS Code tasks.json and execute tasks.

**Parameters**:
- `task` (required): Task definition (label, type, command, args)
- `workspaceFolder` (required): Absolute workspace path

**Use**: Build, run, or custom tasks based on project structure.

---

## GitHub MCP Server

Complete GitHub repository integration via Model Context Protocol.

### Repository Management

#### github_create_repository
Create new repository in account or organization.

**Parameters**:
- `name` (required): Repository name
- `description` (optional): Repository description
- `private` (optional): Boolean for visibility
- `autoInit` (optional): Initialize with README
- `organization` (optional): Org name (omit for personal)

#### github_fork_repository
Fork a repository to account or organization.

**Parameters**:
- `owner` (required): Repository owner
- `repo` (required): Repository name
- `organization` (optional): Org to fork to

#### github_create_branch
Create new branch in repository.

**Parameters**:
- `owner` (required): Repository owner
- `repo` (required): Repository name
- `branch` (required): New branch name
- `from_branch` (optional): Source branch (defaults to repo default)

#### github_create_or_update_file
Create or update a single file remotely on GitHub.

**Parameters**:
- `owner` (required): Repository owner
- `repo` (required): Repository name
- `path` (required): File path in repo
- `content` (required): File contents
- `message` (required): Commit message
- `branch` (required): Branch name
- `sha` (optional): Required for updates (blob SHA of existing file)

**Use**: Remote file operations; use local tools for workspace files.

#### github_push_files
Push multiple files to repository in single commit.

**Parameters**:
- `owner` (required): Repository owner
- `repo` (required): Repository name
- `branch` (required): Branch name
- `files` (required): Array of `{path, content}` objects
- `message` (required): Commit message

**Best Practice**: Efficient for bulk remote file operations.

---

### Pull Requests

#### github-pull-request_activePullRequest
Get comprehensive details of active (checked out) PR.

**Returns**: Title, description, changed files, review comments, PR state, status checks, session logs (for Copilot-created PRs).

**Use**: When asked about "current PR" or "active PR".

#### github-pull-request_openPullRequest
Get details of currently visible (but not necessarily checked out) PR.

**Returns**: Same as activePullRequest.

**Use**: When asked about "open PR" or "this PR".

#### github_create_pull_request
Create new pull request.

**Parameters**:
- `owner` (required): Repository owner
- `repo` (required): Repository name
- `title` (required): PR title
- `head` (required): Branch with changes
- `base` (required): Branch to merge into
- `body` (optional): PR description
- `draft` (optional): Boolean for draft PR
- `maintainer_can_modify` (optional): Allow maintainer edits

#### github_update_pull_request
Update existing pull request.

**Parameters**:
- `owner` (required): Repository owner
- `repo` (required): Repository name
- `pullNumber` (required): PR number
- `title` (optional): New title
- `body` (optional): New description
- `state` (optional): `open` or `closed`
- `base` (optional): New base branch
- `draft` (optional): Draft status
- `reviewers` (optional): Array of GitHub usernames
- `maintainer_can_modify` (optional): Boolean

#### github_merge_pull_request
Merge a pull request.

**Parameters**:
- `owner` (required): Repository owner
- `repo` (required): Repository name
- `pullNumber` (required): PR number
- `merge_method` (optional): `merge`, `squash`, or `rebase`
- `commit_title` (optional): Merge commit title
- `commit_message` (optional): Merge commit message details

#### github_update_pull_request_branch
Update PR branch with latest changes from base branch.

**Parameters**:
- `owner` (required): Repository owner
- `repo` (required): Repository name
- `pullNumber` (required): PR number
- `expectedHeadSha` (optional): Expected SHA of PR's HEAD

#### github_request_copilot_review
Request automated Copilot code review for PR.

**Parameters**:
- `owner` (required): Repository owner
- `repo` (required): Repository name
- `pullNumber` (required): PR number

**Use**: Before requesting human reviewers for automated feedback.

#### github_pull_request_read
Get specific PR data (details, diff, status, files, comments, reviews).

**Parameters**:
- `owner` (required): Repository owner
- `repo` (required): Repository name
- `pullNumber` (required): PR number
- `method` (required): `get`, `get_diff`, `get_status`, `get_files`, `get_review_comments`, `get_reviews`, `get_comments`
- `page` (optional): Page number for pagination
- `perPage` (optional): Results per page (1-100)

**Methods**:
- `get` - PR details
- `get_diff` - Unified diff of changes
- `get_status` - Build/check status
- `get_files` - List of changed files (paginated)
- `get_review_comments` - Line-specific review comments (paginated)
- `get_reviews` - Review summaries
- `get_comments` - General PR comments (paginated)

#### github_list_pull_requests
List PRs in repository with filtering.

**Parameters**:
- `owner` (required): Repository owner
- `repo` (required): Repository name
- `state` (optional): `open`, `closed`, or `all`
- `head` (optional): Filter by head user/org and branch
- `base` (optional): Filter by base branch
- `sort` (optional): `created`, `updated`, `popularity`, `long-running`
- `direction` (optional): `asc` or `desc`
- `page` (optional): Page number
- `perPage` (optional): Results per page (1-100)

**Note**: For author filtering, use github_search_pull_requests instead.

#### github_search_pull_requests
Search PRs using GitHub search syntax (automatically scoped to `is:pr`).

**Parameters**:
- `query` (required): Search query (GitHub search syntax)
- `owner` (optional): Repository owner
- `repo` (optional): Repository name
- `sort` (optional): Sort field (`comments`, `reactions`, `created`, `updated`, etc.)
- `order` (optional): `asc` or `desc`
- `page` (optional): Page number
- `perPage` (optional): Results per page (1-100)

**Example queries**:
- `author:username` - PRs by specific author
- `label:bug` - PRs with bug label
- `is:draft` - Draft PRs
- `reviewed-by:username` - PRs reviewed by user

---

### Issues

#### github-pull-request_issue_fetch
Get issue details as JSON.

**Parameters**:
- `issueNumber` (required): Issue number
- `repo` (optional): `{owner, name}` object

#### github_issue_write
Create or update issues.

**Parameters**:
- `method` (required): `create` or `update`
- `owner` (required): Repository owner
- `repo` (required): Repository name
- `issue_number` (optional): Required for `update` method
- `title` (optional): Issue title (required for `create`)
- `body` (optional): Issue body
- `state` (optional): `open` or `closed`
- `state_reason` (optional): `completed`, `not_planned`, `duplicate`
- `duplicate_of` (optional): Issue number (when state_reason is `duplicate`)
- `labels` (optional): Array of label names
- `assignees` (optional): Array of GitHub usernames
- `milestone` (optional): Milestone number
- `type` (optional): Issue type (if repository has issue types configured)

#### github-pull-request_suggest-fix
Summarize issue and suggest a fix.

**Parameters**:
- `issueNumber` (required): Issue number
- `repo` (optional): `{owner, name}` object

#### github-pull-request_renderIssues
Render issue search results as markdown table (displayed directly to user).

**Parameters**:
- `arrayOfIssues` (required): Array of issue objects
- `totalIssues` (required): Total count

**Note**: No further display needed after this tool.

#### github_assign_copilot_to_issue
Assign Copilot to implement an issue, resulting in a PR with source code changes.

**Parameters**:
- `owner` (required): Repository owner
- `repo` (required): Repository name
- `issueNumber` (required): Issue number

**Outcome**: Copilot creates branch, implements changes, opens PR.

**Documentation**: https://docs.github.com/en/copilot/using-github-copilot/using-copilot-coding-agent-to-work-on-tasks/about-assigning-tasks-to-copilot

---

### Repository Information

#### github_get_teams
Get teams the user is a member of.

**Parameters**:
- `user` (optional): Username (defaults to authenticated user)

**Returns**: Teams in organizations accessible with current credentials.

#### github_repo
Search repository code on GitHub.

**Parameters**:
- `repo` (required): Format `owner/repo`
- `query` (required): Search query with all relevant context

**Use**: Search specific GitHub repos (not open workspaces).

---

### Additional GitHub Tools (Activate as Needed)

#### activate_github_search_tools
- `github-pull-request_formSearchQuery` - Convert natural language to GitHub search query
- `github-pull-request_doSearch` - Execute search on GitHub

#### activate_file_management_tools
- File deletion
- Get file/directory contents

#### activate_commit_and_issue_tools
- Commit details
- Issue details
- List issues
- Tag information
- User profiles

#### activate_release_and_tag_management_tools
- List releases
- Get release details
- Get latest release
- List/get git tags

#### activate_branch_and_commit_tools
- List branches
- Get commit history for branches

#### activate_pull_request_review_tools
- Add comments to pending reviews
- Create and submit reviews
- Delete reviews

#### activate_search_and_discovery_tools
- Search code
- Search repositories
- Search users

---

## Hugging Face MCP Server

AI model and dataset discovery on Hugging Face Hub.

### Authentication

#### mcp_evalstate_hf-_hf_whoami
Check authenticated user for Hugging Face tools.

**Returns**: Username (currently authenticated as `groberts`).

### Search & Discovery

#### mcp_evalstate_hf-_paper_search
Search ML research papers on Hugging Face.

**Parameters**:
- `query` (required): Semantic search query (3-200 chars)
- `results_limit` (optional): Number of results (default 12)
- `concise_only` (optional): Return 2-sentence summaries (for broad searches)

**Returns**: Papers with "Link to paper" to include in results.

**Tip**: Consider tabulating results based on user intent.

#### mcp_evalstate_hf-_space_search
Find Hugging Face Spaces with semantic search.

**Parameters**:
- `query` (required): Search query (1-100 chars)
- `limit` (optional): Number of results (default 10)
- `mcp` (optional): Only return MCP Server enabled Spaces

**Returns**: Spaces with links to include in results.

### Image Generation

#### mcp_evalstate_hf-_gr1_flux1_schnell_infer
Generate images using Flux 1 Schnell model.

**Parameters**:
- `prompt` (required): Image description (60-70 words max)
- `width` (optional): 256-2048 (default 1024)
- `height` (optional): 256-2048 (default 1024)
- `num_inference_steps` (optional): 1-16 (default 4)
- `seed` (optional): 0-2147483647
- `randomize_seed` (optional): Boolean (default true)

### Additional Hugging Face Tools (Activate as Needed)

#### activate_hugging_face_model_and_dataset_tools
- Model search and details
- Dataset search and details
- Repository info (auto-detect model/dataset/space)

#### activate_hugging_face_documentation_tools
- Search documentation
- Fetch detailed docs
- Explore documentation structure
- Handle large docs in chunks

---

## Web/Documentation MCP

### fetch_webpage
Fetch and summarize webpage content.

**Parameters**:
- `urls` (required): Array of URLs
- `query` (required): What to search for in content

**Use**: Summarizing or analyzing webpage content.

### mcp_microsoft_mar_convert_to_markdown
Convert URI to markdown.

**Parameters**:
- `uri` (required): http:, https:, file:, or data: URI

### open_simple_browser
Preview website in VS Code Simple Browser.

**Parameters**:
- `url` (required): http or https URL

**Use**: View locally hosted websites or resources in editor.

---

## AI Development Toolkit

Specialized tools for AI/Agent application development.

### aitk-get_agent_code_gen_best_practices
Essential guidance for any AI agent development.

**Parameters**:
- `requiredHost` (optional): `GitHub`, `Foundry`, or `other`
- `moreIntent` (optional): Additional development intent

**When to Call**: Before creating/scaffolding new AI or Agent app, or adjusting existing one to be agentic.

### aitk-get_ai_model_guidance
Expert guidance for choosing and using AI models.

**Parameters**:
- `preferredHost` (required): Array of `GitHub`, `Foundry`, `OpenAI`, `Anthropic`, `Google`, or `other`
- `currentModel` (optional): Model currently using
- `moreIntent` (optional): Additional model usage intent

**When to Call**: When user has model-related ask, or to adjust existing app's model-related content.

### aitk-evaluation_planner
Multi-turn conversation to clarify evaluation metrics and test dataset.

**When to Call**: FIRST before evaluation code generation when metrics are unclear or incomplete.

### aitk-get_evaluation_code_gen_best_practices
Best practices for evaluation code generation.

**Parameters**:
- `evaluationMetrics` (optional): Array of specific evaluation goals (ONLY when user explicitly describes them)
- `dataset` (optional): Test dataset description
- `language` (optional): Programming language (default `python`)
- `evaluationSdk` (optional): Evaluation SDK (default `azure-ai-evaluation`)

**When to Call**: When working on evaluation for AI application or AI agent.

### aitk-evaluation_agent_runner_best_practices
Guidance for using agent runners to collect responses for evaluation.

**Parameters**:
- `sdk` (optional): `agent-framework` or `others`

**Returns**: SDK-specific guidance for executing AI applications with test datasets.

### aitk-convert_declarative_agent_to_code
Convert declarative agent specifications to runnable code.

**Parameters**:
- `language` (optional): `Python` (default) or `.NET`

**Returns**: Best practices and code samples for converting specs to agent code.

### aitk-get_agent_model_code_sample
Code samples for AI Agent and AI Model development.

**Parameters**:
- `category` (required): `Agent`, `Chat`, `MultiAgents`, or `Workflow`
- `host` (required): `GitHub`, `Foundry`, or `other`
- `language` (required): `Python`, `Node.js`, `.NET`, `Java`, or `other`

**When to Call**: For any code generation involving AI Agents and AI Models.

### activate_ai_agent_development_best_practices
Activate additional AI agent development tools and guidance.

---

## Command Line Tools

### GitHub CLI (gh)

Available via `run_in_terminal`:

**PR Management**:
```powershell
gh pr list                    # List PRs
gh pr view 44                 # View PR #44
gh pr create --title "..." --body "..."  # Create PR
gh pr merge 44 --squash       # Merge PR with squash
```

**Issue Management**:
```powershell
gh issue list                 # List issues
gh issue create --title "..." --body "..."  # Create issue
gh issue view 123             # View issue #123
```

**Repository Operations**:
```powershell
gh repo view                  # View repo info
gh repo clone owner/repo      # Clone repository
gh workflow list              # List workflows
gh run list                   # List workflow runs
```

**Release Management**:
```powershell
gh release list               # List releases
gh release create v1.0.0      # Create release
```

### Git Operations

Via `run_in_terminal`:

```powershell
git status                    # Check status
git add -A                    # Stage all changes
git commit -m "Message"       # Commit with message
git push                      # Push to remote
git pull                      # Pull from remote
git branch                    # List branches
git checkout -b feature-name  # Create and switch to branch
git log --oneline -10         # View recent commits
```

### VS Code Commands

Via `run_vscode_command`:
- Execute VS Code commands programmatically
- Install extensions with `install_extension`
- Manage workspace settings

---

## Tool Selection Strategy

### For File Operations

| Task | Tool | Notes |
|------|------|-------|
| Read local files | `read_file` | Use offset/limit for large files |
| Create local files | `create_file` | Creates parent directories automatically |
| Edit local files | `replace_string_in_file` | Single edit with context |
| Batch edit local files | `multi_replace_string_in_file` | Most efficient for multiple changes |
| Edit remote GitHub files | `github_create_or_update_file` | Single file on GitHub |
| Bulk remote GitHub edits | `github_push_files` | Multiple files in one commit |
| Read PR files | `github_pull_request_read` | Method: `get_diff` or `get_files` |

### For Pull Requests

| Task | Tool | Notes |
|------|------|-------|
| Get active PR | `github-pull-request_activePullRequest` | Currently checked out PR |
| Get open PR | `github-pull-request_openPullRequest` | Currently visible PR |
| PR details/diff | `github_pull_request_read` | Multiple methods available |
| Create PR | `github_create_pull_request` | New pull request |
| Update PR | `github_update_pull_request` | Title, description, reviewers |
| Merge PR | `github_merge_pull_request` | Merge, squash, or rebase |
| Request review | `github_request_copilot_review` | Automated Copilot review |
| List PRs | `github_list_pull_requests` | With filtering |
| Search PRs | `github_search_pull_requests` | GitHub search syntax |

### For Search

| Task | Tool | Notes |
|------|------|-------|
| Semantic local search | `semantic_search` | Natural language queries |
| Exact text search | `grep_search` | Fast, supports regex |
| File pattern search | `file_search` | Glob patterns |
| Code on GitHub | `github_repo` | Specific repository |
| PR/issue search | `github_search_pull_requests` | GitHub search syntax |
| Find code usages | `list_code_usages` | References, definitions |

### For Testing

| Task | Tool | Notes |
|------|------|-------|
| Run tests | `runTests` | Preferred, with coverage |
| Run tests in terminal | `run_in_terminal` | Alternative with pytest |
| Get IDE errors | `get_errors` | Compile/lint diagnostics |

### For AI Development

| Task | Tool | Notes |
|------|------|-------|
| Agent development | `aitk-get_agent_code_gen_best_practices` | Always call first |
| Model selection | `aitk-get_ai_model_guidance` | Model-related tasks |
| Plan evaluation | `aitk-evaluation_planner` | When metrics unclear |
| Evaluation code | `aitk-get_evaluation_code_gen_best_practices` | Evaluation implementation |

---

## Best Practices

### 1. Batch Operations
**Do**: Use `multi_replace_string_in_file` for multiple edits
**Don't**: Call `replace_string_in_file` sequentially

**Example**:
```markdown
# Good
Prompt: "Update all test files to use new fixture pattern"
→ Uses multi_replace_string_in_file

# Bad
Prompt: "Update test_bot.py, then test_channel.py, then test_user.py..."
→ Sequential replace_string_in_file calls
```

### 2. Parallel Reads
**Do**: Read multiple files in parallel when gathering context
**Don't**: Read files one at a time sequentially

**Example**:
```markdown
# Good
Prompt: "Read lib/bot.py, common/config.py, and tests/unit/test_bot.py 
to understand the initialization flow"
→ Parallel read_file calls

# Bad
Prompt: "Read lib/bot.py"
[wait for response]
Prompt: "Now read common/config.py"
[wait for response]
...
```

### 3. GitHub Integration
**Prefer**: GitHub MCP tools over `gh` CLI for automation
**Use**: `gh` CLI for interactive or one-off operations

**Example**:
```markdown
# Automation (MCP)
→ github_create_pull_request with parameters

# Interactive (CLI)
→ run_in_terminal: "gh pr create"  # Opens editor
```

### 4. Error Checking
**Always**: Use `get_errors` after file edits to validate changes

**Example**:
```markdown
Prompt: "Update lib/bot.py to add new method, then check for any errors"
→ replace_string_in_file, then get_errors
```

### 5. Test Execution
**Prefer**: `runTests` over terminal pytest commands when possible
**Benefit**: Better integration, coverage reporting, structured output

### 6. Tool Discovery
**Activate**: Specialized tool groups only when needed
**Why**: Reduces tool namespace, improves performance

**Example**:
```markdown
# When needed
Prompt: "I need to search issues by custom criteria"
→ activate_github_search_tools

# Not by default
→ Don't pre-activate all possible tools
```

### 7. Context Management
**Use**: Pagination for large result sets (5-10 items per batch)
**Use**: `minimal_output` parameter when full details not needed

**Example**:
```markdown
# Paginated
→ github_list_pull_requests with page=1, perPage=10

# Minimal output (when available)
→ Use minimal_output=true for overview
```

### 8. Python Environment
**Always**: Call `configure_python_environment` before Python operations
**Then**: Use specialized Python tools for package management

---

**Document Version**: 1.0  
**Last Updated**: November 21, 2025  
**See Also**: [AGENTS.md](../../AGENTS.md), [AGENT_WORKFLOW_DETAILED.md](AGENT_WORKFLOW_DETAILED.md), [AGENT_PROMPTING_GUIDE.md](AGENT_PROMPTING_GUIDE.md)
