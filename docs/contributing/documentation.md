---
description: Write and verify TestSeal documentation for Read the Docs.
---

# Documentation

The documentation uses MkDocs Material and is hosted on Read the Docs. Sources
live under `docs/`; navigation and theme configuration live in `mkdocs.yml`.

## Install documentation dependencies

```bash
python -m pip install -r docs/requirements.txt
```

Versions are pinned so local, CI, and Read the Docs builds use the same toolchain.

## Preview locally

```bash
python -m mkdocs serve
```

Open `http://127.0.0.1:8000`. Live reload rebuilds changed pages.

## Run the strict build

```bash
python -m mkdocs build --strict
```

Strict mode fails for missing navigation pages, omitted documents, broken
relative links, missing anchors, and other warnings. Generated output is written
to `.docs-site/` and ignored by Git.

## Content structure

- **Get started:** a new user's shortest path to a successful scan.
- **Guides:** task-based procedures with a defined outcome.
- **Integrations:** complete setup for external tools.
- **Reference:** exhaustive, factual contracts and defaults.
- **Concepts:** architecture, trust, scope, and design explanation.
- **Contribute:** maintainer workflows.
- **Project:** support, releases, licensing, and citation.

Put information in the narrowest appropriate page and link to it instead of
copying long sections.

## Style

- Lead with the task or fact.
- Use short paragraphs and descriptive headings.
- Prefer exact commands and complete examples.
- Separate defaults from recommendations.
- State limitations beside the affected feature.
- Avoid claims about intent, authorship, or guarantees.
- Avoid promotional filler and decorative language.
- Use `TestSeal`, `GitHub Actions`, `pre-commit`, `pytest`, and `unittest`
  consistently.
- Use repository-relative paths with forward slashes.

## Links

Use relative links between documentation pages:

```markdown
[configuration reference](../reference/configuration.md)
```

Use full HTTPS links for repository-root files and external projects. Include
the `.md` suffix for internal source links so MkDocs validates them and GitHub
can render them.

## Code examples

Examples must be executable or clearly marked as fragments. For GitHub Actions,
include checkout depth, Python setup, permissions, and pinning context in the
complete workflow. Do not include secrets.

When a command has meaningful failure behavior, state the exit code.

## Add a page

1. Create the Markdown file in the correct section.
2. Add front matter with a concise `description`.
3. Add the page to `nav` in `mkdocs.yml`.
4. Link it from the closest parent or related task.
5. Run the strict build.
6. Inspect desktop and narrow viewport rendering.

Read the Docs builds `mkdocs.yml` through `.readthedocs.yaml` using the pinned
requirements file.
