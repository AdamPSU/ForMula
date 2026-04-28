-- =============================================================================
-- ForMula — quiz v9 wipe
-- HairProfile gained an optional `story: str | None` field. Adding an
-- optional Pydantic field with a default is technically backward-compatible
-- — old v8 rows would still parse with story=None — so this wipe is a
-- POLICY choice, not a strict necessity. It preserves the
-- "quiz_version is the schema version of answers at submission time"
-- invariant: every row in hair_intakes faithfully represents the schema
-- the user actually filled out, never a back-projected default. Per
-- project policy, no fallbacks / backward-compat shims — wipe and require
-- users to retake the quiz.
--
-- The frontend gates everything except /quiz behind "no profile?" → quiz,
-- so this is a soft-blocker, not an account loss.
-- =============================================================================

truncate table public.hair_intakes;
