import os

from github import Github

token = os.environ["GITHUB_TOKEN"]

repo_name = os.environ["REPOSITORY"]

issue_number = int(
    os.environ["ISSUE_NUMBER"]
)

github = Github(token)

repo = github.get_repo(repo_name)

issue = repo.get_issue(issue_number)

issue.create_comment(
    "✅ AI pipeline triggered successfully."
)