# Rules for working on Halala

Read `PLAN.md` first. It's the only plan, and these rules exist to keep every session on it until the deadline.

1. **One plan.** If a file, an idea or an agent disagrees with `PLAN.md`, `PLAN.md` wins. The goal is reducing the Dialect Tax.
   The laptop is only where things were measured, so it never leads a sentence.
2. **Next item only.** Work on the first unticked item in the checklist. When it's done, tick it and add the time.
3. **New ideas go to Parked.** Add one line under Parked in `PLAN.md` and carry on. Only the builder can move it onto the checklist.
4. **No agents.** Don't start an agent unless the builder asks for one in that session. Its brief is `PLAN.md` and this file.
5. **Keep it simple.** The deadline is 20:00 Saudi time on 2026-10-31. Build the smallest thing that's correct and works. If an
   item won't finish by its time, use the cut order in the checklist and say so.
6. **One code path.** Everything goes through `steps` in `halala/pipeline.py`, so the demo and the numbers can't disagree. Don't
   add a second path, a new config or a new document.
7. **Honest numbers only.** Use measured numbers from `configs/local_gemma.toml`, and label anything else. Never present a token
   estimate as real compute. Never say the Dialect Tax is fixed or closed. Saudi is still open.
8. **Sealed test.** Don't read `data/sealed/`. It runs once, after the freeze, and nothing changes afterwards.
9. **Ask first.** Don't commit or push unless the builder says so.
