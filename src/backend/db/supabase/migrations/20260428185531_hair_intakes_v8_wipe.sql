-- =============================================================================
-- ForMula — quiz v8 wipe
-- HairProfile schema changed in app code: dropped `drying_method`, added
-- `chemical_treatment` and `heat_tool_frequency`. Existing v7 rows in
-- public.hair_intakes can no longer pass Pydantic validation in
-- profiles.repository.get_latest_hair_profile, so they would 500 on every
-- /me/hair-profile or /filter call. Per project policy, no fallbacks /
-- backward-compat shims — wipe and require users to retake the quiz.
--
-- The frontend gates everything except /quiz behind "no profile?" → quiz,
-- so this is a soft-blocker, not an account loss.
-- =============================================================================

truncate table public.hair_intakes;
