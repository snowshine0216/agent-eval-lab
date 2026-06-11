# SKIPPED — out-of-scope items

## Human annotation labels for judge calibration

The design's calibration protocol (§6) requires ≥2 **human** annotators on a
shared subset, with human–human κ reported *before* judge–human κ. An
autonomous run cannot produce human labels. **Blocker:** needs the project
owner plus a second human annotator. **Unblock path:** item 003 ships the
annotation packet (blind, rubric-anchored, fixed item order) and a
`calibrate` command; the user fills the packet (and recruits annotator #2),
re-runs `calibrate`, and replaces the provisional two-LLM-annotator κ with
the real human–human / judge–human numbers.

## `openrouter:openai/gpt-5.5` live condition

Unreachable from this network: direct calls are China region-blocked and the
available proxy exits a ToS-flagged datacenter subnet (AS13410), so premium
providers reject the IP. Environmental, not a harness defect — open models
route through the same proxy fine. **Unblock path:** a residential-exit proxy
or running validation from an unblocked network; the condition is config-only
(`--provider openrouter`) once reachable.

## Multi-turn `ScriptedUser` / `ask_user` clarification tasks

Roadmap places the deterministic scripted-user protocol in Weeks 9-10. The
"deliberate ambiguity (forces ask_user)" difficulty knob is deferred with it;
v2 hardness comes from multi-step depth, distractor tools, argument
complexity, state-dependent reasoning, and trajectory constraints instead.
