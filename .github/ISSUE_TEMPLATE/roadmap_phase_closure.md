---
name: Roadmap phase closure
about: Checklist when closing or re-verifying a ROADMAP phase against code and CI
title: "closure: phase N — "
labels: ["documentation"]
---

## Summary

Describe what changed and link `docs/ROADMAP.md` §5 phase section.

## Evidence

- [ ] `make check` (or CI equivalent) green on the merge commit
- [ ] Every acceptance-criterion row has a pointer to **tests** or **manual evidence**
- [ ] `docs/ROADMAP.md` **Recent landings** + phase **PR refs** updated
- [ ] API contract changes reflected in `PRD.md` §5 and/or `docs/API.md`

## Notes

Screenshots / keys required from maintainers (if any):
