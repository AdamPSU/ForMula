-- =============================================================================
-- Fourth brand-seed wave — 12 brands filling Tavily-surfaced coverage gaps
-- that the first three waves missed: thinning / density, scalp condition,
-- bond-repair peptides, men-focused, Asian-pro, Ayurvedic, blonde-toning,
-- protein reconstruction, eco / zero-waste bars, kids / baby, and gray-hair
-- + Latinx. Idempotent on slug.
-- =============================================================================

insert into brands (slug, name, website_url, tier) values
  -- Thinning / aging / menopausal / density
  ('better-not-younger',   'Better Not Younger',    'https://betternotyounger.com',      'luxury'),
  ('nioxin',               'Nioxin',                'https://www.nioxin.com',            'luxury'),
  -- Bond repair / peptide
  ('k18',                  'K18',                   'https://www.k18hair.com',           'luxury'),
  -- Men-focused
  ('american-crew',        'American Crew',         'https://www.americancrew.com',      'everyday'),
  -- Asian-market professional
  ('shiseido-professional','Shiseido Professional', 'https://shiseidoprofessional.com',  'luxury'),
  -- South Asian / Ayurvedic
  ('kama-ayurveda',        'Kama Ayurveda',         'https://www.kamaayurveda.com',      'luxury'),
  -- Blonde / silver / purple-toning
  ('pravana',              'Pravana',               'https://www.pravana.com',           'luxury'),
  -- Protein / reconstruction
  ('aphogee',              'ApHogee',               'https://aphogee.com',               'everyday'),
  -- Eco / bar / zero-waste
  ('ethique',              'Ethique',               'https://ethique.com',               'everyday'),
  -- Kids / baby gentle
  ('honest',               'Honest',                'https://honest.com',                'everyday'),
  ('burts-bees-baby',      'Burt''s Bees Baby',     'https://www.burtsbees.com',         'everyday'),
  -- Gray-hair + Latinx-founded
  ('arey',                 'Arey',                  'https://arey.com',                  'luxury')
on conflict (slug) do update set
  name        = excluded.name,
  website_url = excluded.website_url,
  tier        = excluded.tier;
