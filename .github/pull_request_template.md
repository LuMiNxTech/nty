## What and why

<!-- What does this change do, and why is it needed? Link related issues. -->

## Checklist

- [ ] Tests cover the change (unit, snapshot or end-to-end)
- [ ] `cargo fmt`, `cargo clippy -D warnings` and `cargo test` pass locally
- [ ] User-facing behaviour (CLI, protocol, configuration) is documented, and schema snapshots are updated
- [ ] No breaking change to a public schema (or the protocol major version is bumped)
- [ ] New or upgraded dependencies are justified, with their binary size and startup impact listed below
- [ ] stdout carries only results or protocol output

## Dependency impact (if any)

| Dependency | Why | Binary size Δ | Startup Δ |
|---|---|---|---|
