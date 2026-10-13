#! /bin/bash

# If changes are found then create a PR with the changes.
# Skip creation when an open PR against the same base already has the
# same list.json content.

set -e

PR_TITLE=$1
if [ -z "$PR_TITLE" ]; then
    PR_TITLE="Auto PR: Differences detected"
fi

BRANCH=$2
if [ -z "$BRANCH" ]; then
    BRANCH="main"
fi

# Check if GitHub CLI is installed
if ! command -v gh &> /dev/null; then
    echo "Error: GitHub CLI (gh) is not installed."
    exit 1
fi

if [ -z "$GITHUB_TOKEN" ]; then
    echo "GITHUB_TOKEN is not set."
    exit 1
else
    echo "GITHUB_TOKEN is set."
fi

if [ "$BRANCH" = "main" ]; then
    BASE_BRANCH="$BRANCH"
else
    BASE_BRANCH="rel/$BRANCH"
fi

FILE_PATH=".github/get_predefined_de/catalog/list.json"

# Blob id of the list.json that git add would commit.
local_list_json_sha() {
    local tmp_index sha
    tmp_index=$(mktemp)
    rm -f "$tmp_index"
    GIT_INDEX_FILE="$tmp_index" git add -- "$FILE_PATH"
    sha=$(GIT_INDEX_FILE="$tmp_index" git rev-parse --verify ":$FILE_PATH")
    rm -f "$tmp_index"
    printf '%s\n' "$sha"
}

# Blob id of list.json at a commit. Falls back to walking the git tree when
# the file is too large for the contents API.
list_json_sha_at_ref() {
    local ref=$1
    local sha tree
    if sha=$(gh api "repos/{owner}/{repo}/contents/${FILE_PATH}?ref=${ref}" --jq .sha 2>/dev/null); then
        if [ -n "$sha" ] && [ "$sha" != "null" ]; then
            printf '%s\n' "$sha"
            return 0
        fi
    fi

    tree=$(gh api "repos/{owner}/{repo}/commits/${ref}" --jq .commit.tree.sha)
    tree=$(gh api "repos/{owner}/{repo}/git/trees/${tree}" --jq '.tree[] | select(.path==".github") | .sha')
    tree=$(gh api "repos/{owner}/{repo}/git/trees/${tree}" --jq '.tree[] | select(.path=="get_predefined_de") | .sha')
    tree=$(gh api "repos/{owner}/{repo}/git/trees/${tree}" --jq '.tree[] | select(.path=="catalog") | .sha')
    sha=$(gh api "repos/{owner}/{repo}/git/trees/${tree}" --jq '.tree[] | select(.path=="list.json") | .sha')
    printf '%s\n' "$sha"
}

# Prints the URL of the first open PR whose list.json matches. Prints nothing otherwise.
find_open_pr_with_same_list_json() {
    local base=$1
    local local_sha pr_list number url head_sha remote_sha
    local_sha=$(local_list_json_sha)
    pr_list=$(mktemp)

    gh pr list --base "$base" --state open --limit 200 --json number,url,headRefOid --jq '.[] | [.number, .url, .headRefOid] | @tsv' > "$pr_list"
    while IFS=$'\t' read -r number url head_sha; do
        [ -n "$head_sha" ] || continue
        if remote_sha=$(list_json_sha_at_ref "$head_sha"); then
            if [ "$remote_sha" = "$local_sha" ]; then
                printf '%s\n' "$url"
                rm -f "$pr_list"
                return 0
            fi
        fi
    done < "$pr_list"

    rm -f "$pr_list"
}

echo "Checking update for branch: $BRANCH"

if [[ `git status --porcelain` ]]; then
    echo "Found changes"

    # Check if the file exists, and create it if it doesn't.
    # Do this before the PR comparison so the content matches the commit.
    if [ ! -f "$FILE_PATH" ]; then
        echo "File $FILE_PATH does not exist. Creating a new file..."
        mkdir -p "$(dirname "$FILE_PATH")"  # Ensure the directory exists
        echo "{}" > "$FILE_PATH"  # Create an empty JSON file
        echo "Created $FILE_PATH with default content."
    fi

    echo "Checking open pull requests against $BASE_BRANCH for the same list.json..."
    SAME_PR=$(find_open_pr_with_same_list_json "$BASE_BRANCH")
    if [ -n "$SAME_PR" ]; then
        echo "An open pull request already has the same list.json: $SAME_PR"
        echo "No new pull request was created."
        exit 0
    fi

    # Configure Git user identity
    echo "Configuring Git user identity..."
    git config --global user.name "GitHub Actions"
    git config --global user.email "actions@github.com"

    # Create a new branch for the changes
    BRANCH_NAME="predefined_de/autopr_$(date +%s)"
    echo "Creating a new branch: $BRANCH_NAME"
    git checkout -b "$BRANCH_NAME"

    # Stage all changes, including untracked files
    echo "Staging and committing changes..."
    git add -A
    git commit -m "$PR_TITLE"

    # Push the branch to the remote repository
    echo "Pushing changes to remote repository..."
    git push -u origin "$BRANCH_NAME"

    # Create a pull request using GitHub CLI
    echo "Creating a pull request..."
    BODY_CONTENT="Automated PR: Differences detected between the existing file and the generated content."
    gh pr create --title "$PR_TITLE" --body "$BODY_CONTENT" --base "$BASE_BRANCH" --head "$BRANCH_NAME"
else
    echo "No changes to commit"
fi
