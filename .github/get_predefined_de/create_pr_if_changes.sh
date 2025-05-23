#! /bin/bash

# If changes are found then create a PR with the changes

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

echo "Checking update for branch: $BRANCH"

if [[ `git status --porcelain` ]]; then
    echo "Found changes"

    # Configure Git user identity
    echo "Configuring Git user identity..."
    git config --global user.name "GitHub Actions"
    git config --global user.email "actions@github.com"

    # Create a new branch for the changes
    BRANCH_NAME="predefined_de/autopr_$(date +%s)"
    echo "Creating a new branch: $BRANCH_NAME"
    git checkout -b "$BRANCH_NAME"

    # Check if the file exists, and create it if it doesn't
    FILE_PATH=".github/get_predefined_de/catalog/list.json"
    if [ ! -f "$FILE_PATH" ]; then
        echo "File $FILE_PATH does not exist. Creating a new file..."
        mkdir -p "$(dirname "$FILE_PATH")"  # Ensure the directory exists
        echo "{}" > "$FILE_PATH"  # Create an empty JSON file
        echo "Created $FILE_PATH with default content."
    fi

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
    if [[ "$BRANCH" == "main" ]]; then
        gh pr create --title "$PR_TITLE" --body "$BODY_CONTENT" --base "$BRANCH" --head "$BRANCH_NAME"
    else
        gh pr create --title "$PR_TITLE" --body "$BODY_CONTENT" --base "rel/$BRANCH" --head "$BRANCH_NAME"
    fi
else
    echo "No changes to commit"
fi
