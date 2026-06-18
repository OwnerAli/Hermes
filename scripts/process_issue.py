import json
import os
import re
import subprocess

from github import Github, Auth
from google import genai
from git import Repo


# ---------------------------
# CONFIG
# ---------------------------

WORKDIR = os.getcwd()
SKILL_DIR = os.path.join(WORKDIR, "skills")

FIELD_LABELS = ("Plugin", "Skill", "Description")

FIELD_PATTERN = re.compile(
    rf"^#{{1,6}}\s*({'|'.join(FIELD_LABELS)})\s*$",
    re.MULTILINE
)

PLUGIN_REPOS = {
    "Xenith": "OwnerAli/Xenith",
    "Jetpacks": "OwnerAli/Jetpacks",
    "CustomDrops": "OwnerAli/CustomDrops",
}


# ---------------------------
# HELPERS
# ---------------------------

def parse_issue_fields(body: str) -> dict:
    matches = list(FIELD_PATTERN.finditer(body))
    fields = {}

    for i, m in enumerate(matches):
        label = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        value = body[start:end].strip()
        fields[label] = None if value == "_No response_" else value

    return fields


def load_skill_prompt(skill_name: str):
    path = os.path.join(
        SKILL_DIR,
        skill_name.lower(),
        "prompt.md"
    )

    if not os.path.exists(path):
        return None

    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def load_skill_manifest(skill_name: str):
    path = os.path.join(
        SKILL_DIR,
        skill_name.lower(),
        "manifest.json"
    )

    if not os.path.exists(path):
        return {}

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def read_file(path: str):
    if not os.path.exists(path):
        print(f"Missing context file: {path}")
        return None

    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def build_context(target_dir: str, manifest: dict):
    sections = []

    for file_path in manifest.get("context", []):
        full_path = os.path.join(target_dir, file_path)

        content = read_file(full_path)

        if content:
            sections.append(
                f"""
FILE: {file_path}

{content}
"""
            )

    for file_path in manifest.get("examples", []):
        full_path = os.path.join(target_dir, file_path)

        content = read_file(full_path)

        if content:
            sections.append(
                f"""
EXAMPLE: {file_path}

{content}
"""
            )

    return "\n\n".join(sections)


def run(cmd):
    print(">", " ".join(cmd))
    subprocess.check_call(cmd)


# ---------------------------
# MAIN
# ---------------------------

def main():
    issue_number = int(os.environ["ISSUE_NUMBER"])
    repo_full = os.environ["REPOSITORY"]
    token = os.environ["OWNERALI_PAT"]

    gh = Github(auth=Auth.Token(token))
    repo = gh.get_repo(repo_full)
    issue = repo.get_issue(issue_number)

    body = os.environ["ISSUE_BODY"]

    fields = parse_issue_fields(body)

    plugin = fields.get("Plugin")
    skill = fields.get("Skill")
    description = fields.get("Description")

    target_repo = PLUGIN_REPOS.get(plugin)

    if not target_repo:
        issue.create_comment(f"Unknown plugin: `{plugin}`")
        return

    skill_prompt = load_skill_prompt(skill or "")
    manifest = load_skill_manifest(skill or "")

    if not skill_prompt:
        issue.create_comment(f"Skill not found: `{skill}`")
        return

    gemini_api_key = os.environ.get("GEMINI_API_KEY")

    if not gemini_api_key:
        issue.create_comment("Missing GEMINI_API_KEY")
        return

    # ---------------------------
    # Clone target repo
    # ---------------------------

    branch_name = f"ai/issue-{issue_number}"
    target_dir = os.path.join(WORKDIR, "target")

    if os.path.exists(target_dir):
        subprocess.run(
            ["rm", "-rf", target_dir],
            check=True
        )

    run([
        "git",
        "clone",
        f"https://x-access-token:{token}@github.com/{target_repo}.git",
        target_dir
    ])

    # ---------------------------
    # Load architecture context
    # ---------------------------

    context = build_context(target_dir, manifest)

    print("=== CONTEXT LOADED ===")
    print(context[:10000])
    print("======================")

    # ---------------------------
    # Gemini
    # ---------------------------

    client = genai.Client(api_key=gemini_api_key)

    prompt = """
You are an expert Java Minecraft plugin developer.

## SKILL RULES
{skill_prompt}

## PROJECT
Plugin: {plugin}

## TASK
{description}

## EXISTING ARCHITECTURE
{context}

## RULES

- Follow existing architecture patterns.
- Reuse existing code conventions.
- If registration is required, update the relevant registry.
- Do not invent architecture.

Return ONLY files in this format:

<file path="src/.../Example.java">
public class Example {{ }}
</file>

No explanations.
No markdown.
Only file tags.
""".format(
        skill_prompt=skill_prompt,
        plugin=plugin,
        description=description,
        context=context
    )

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )

    output = response.text

    print("=== GEMINI OUTPUT ===")
    print(output)
    print("=====================")

    files = re.findall(
        r'<file path="(.*?)">(.*?)</file>',
        output,
        re.DOTALL
    )

    if not files:
        issue.create_comment("No files generated by AI.")
        return

    # ---------------------------
    # Create branch
    # ---------------------------

    repo_git = Repo(target_dir)
    repo_git.git.checkout("-b", branch_name)

    # ---------------------------
    # Write files
    # ---------------------------

    for path, content in files:
        full_path = os.path.join(target_dir, path)

        os.makedirs(
            os.path.dirname(full_path),
            exist_ok=True
        )

        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content.strip())

        print(f"Written: {path}")

    # ---------------------------
    # Commit + Push
    # ---------------------------

    repo_git.git.add(all=True)

    repo_git.index.commit(
        f"AI: Implement {skill} for issue #{issue_number}"
    )

    repo_git.git.push(
        "--set-upstream",
        "origin",
        branch_name
    )

    # ---------------------------
    # PR
    # ---------------------------

    target_github_repo = gh.get_repo(target_repo)

    pr = target_github_repo.create_pull(
        title=f"[AI] {skill} - Issue #{issue_number}",
        body=f"""
AI-generated implementation.

Plugin: {plugin}
Skill: {skill}

Closes #{issue_number}
""",
        head=branch_name,
        base="main"
    )

    issue.create_comment(
        f"""AI Done!

- Repo: `{target_repo}`
- Branch: `{branch_name}`
- PR: {pr.html_url}
"""
    )

    print("DONE")


if __name__ == "__main__":
    main()