# kroki-session policies — placeholder for v2

v1 of kroki-session is reactive: mode=end renders whatever changed. No policy guidance.

v2 will populate this directory with YAML rules mapping `{domain, role, phase}` → recommended diagram type set. Rules drawn from SEBoK (Systems Engineering Body of Knowledge), SWEBOK, PMBOK, and Heilmeier method.

When populated, `kroki-session` will read these files to suggest diagrams the user should be producing but hasn't.

See [../../../specs/2026-04-20-plan-5a-kroki-session-skill-design.md](../../../specs/2026-04-20-plan-5a-kroki-session-skill-design.md) §10 for the v2 trigger criteria.
