# Security Policy

## Supported versions

nty is pre-alpha. Until the first release, only the `main` branch receives
security fixes.

## Reporting a vulnerability

Please **do not** open a public issue for security problems. Report them
privately through GitHub's
[private vulnerability reporting](https://github.com/LuMiNxTech/nty/security/advisories/new).

Include a description of the issue, steps to reproduce, the affected version or
commit, and the impact you expect. We aim to acknowledge reports within 7 days.

## Scope notes

nty runs commands and edits files on behalf of a model. By design it:

- trusts the project it runs in, so repository hooks, plugins and skills can
  execute code;
- blocks a set of catastrophic shell commands, but this is a backstop and
  **not a security boundary**;
- does not provide an operating-system sandbox.

Run untrusted repositories inside a container. Reports that rely only on these
documented behaviours are not treated as vulnerabilities, but bypasses of the
command-blocking rules are welcome as regular bug reports.
