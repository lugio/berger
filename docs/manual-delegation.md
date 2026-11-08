# Delegation and missions

This English operational note complements the [French reference manual](manuel.md#courtier).

Use `deleguer:<agent>` for a short question: the delegated agent has seven minutes to answer with sources, using its own authorized access. An open agent retains its authorized direct tools; a strict agent stays within its sandbox and broker permissions. Delegation permits no file changes except the journal, no sending, and no chained delegation. Use a mission for longer work requiring a checklist and deliverables.

Parameters use a JSON array through `--stdin` or `--fichier .transport/requete.json`; positional private parameters are refused. See the French manual for private transport file permissions and examples.

A guard refusal must be reported to the owner, including for read-only work. Passing the refused command through a file or another tool to evade the refusal is forbidden. The owner decides.

The project lead can close an unfinished developer mission after the owner explicitly rejects its current merge request. Berger checks the broker's latest completed decision, its author, request dates and current commit, and records abandonment in the checklist. The refusal record must not predate the current mission, including when both events occur within the same minute. A pending validation, another actor's refusal, a failed action, an old request or another commit does not qualify. Existing checks against losing uncommitted or unpushed work still apply.

The installation self-test expects scheduled Herdr agents during their configured hours (inclusive boundaries), and always expects agents with active missions. Agents requested on demand without a mission are excluded. Delegation probes use compatible strict Codex agents and JSON transport; an unavailable pair is reported as `INFO`, and an unrelated error cannot prove an authorization refusal.
