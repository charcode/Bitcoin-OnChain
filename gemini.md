# Gemini Bootstrap

Read [agents.md](agents.md) first.

Then recursively read all Markdown files linked from `agents.md` and from each follow-up Markdown file before making changes.

Minimum required reading set:

- [agents.md](agents.md)
- [architecture.md](architecture.md)
- [dev-protocol.md](dev-protocol.md)
- [todo.md](todo.md)
- [README.md](README.md)

Operating rules:

- Treat `agents.md` as the source of truth for agent initialization.
- Follow `dev-protocol.md` for modularity, encapsulation, and testing expectations.
- Update `todo.md` when you discover missing work, drift, or unresolved decisions.
- Preserve the separation between live mempool estimation, historical block stencil analysis, and optional external price comparison.

Do not modify code before the recursive Markdown pass is complete.
