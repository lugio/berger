# Security policy

## Report privately

Use GitHub's **Private vulnerability reporting** for this repository.
Open the repository's **Security** tab and select **Report a vulnerability**
to create a private security advisory. Do not open a public issue or pull
request containing vulnerability details. No reporting email is published.

Include the affected commit or version, prerequisites, reproducible steps
using fictional data, expected and actual behavior, and the impact you observed.
Never attach real credentials, browser sessions, secret stores, personal agent
journals or data belonging to someone else.

If the private reporting control is unavailable, do not post sensitive details
publicly. The repository administrators must enable private reporting first.
This document does not assert that a repository setting has already been changed.

## Scope and support

Reports about the current main branch and the latest documented version are
welcome. There is no maintained backport branch or guaranteed response deadline.
Please allow private investigation and coordination before public disclosure.

Berger's protections depend on the host, the engine version, the selected agent
mode and successful admission tests. A model-free test suite is not proof that
a particular engine release enforces its sandbox. Read the
[reference manual's security section](docs/manuel.md#sécurité-identique-pour-chaque-agent-et-chaque-moteur)
and run the installation's admission tests before relying on that boundary.
An agent deliberately configured with an open wall has different protections.

The MIT license supplies the software without warranty; see [LICENSE](LICENSE).
