-- =============================================================================
-- brands.tier — coarse price band so queries can exclude luxury brands when
-- a user opts out of premium recommendations. Binary for now: 'luxury' covers
-- lines whose typical product retails >$30 (Olaplex, Kérastase, Ouai, Oribe,
-- …); 'everyday' covers <$30 brands (Cantu, Mielle, Odele, …). Nullable so
-- brands seeded before classification can still insert.
--
-- Plus a one-shot seed of 30 well-known direct-to-consumer hair brands so the
-- scraper agent no longer has to be hand-fed starting domains. Seed is
-- idempotent on slug: re-running overwrites name / website_url / tier, which
-- lets this same statement fix drift if we edit the list later.
-- =============================================================================

alter table brands add column tier text;

alter table brands add constraint brands_tier_check
  check (tier is null or tier in ('luxury', 'everyday'));

insert into brands (slug, name, website_url, tier) values
  ('olaplex',           'Olaplex',           'https://olaplex.com',              'luxury'),
  ('kerastase',         'Kérastase',         'https://www.kerastase-usa.com',    'luxury'),
  ('oribe',             'Oribe',             'https://www.oribe.com',            'luxury'),
  ('living-proof',      'Living Proof',      'https://www.livingproof.com',      'luxury'),
  ('bumble-and-bumble', 'Bumble and Bumble', 'https://www.bumbleandbumble.com',  'luxury'),
  ('davines',           'Davines',           'https://us.davines.com',           'luxury'),
  ('virtue',            'Virtue',            'https://virtuelabs.com',           'luxury'),
  ('moroccanoil',       'Moroccanoil',       'https://www.moroccanoil.com',      'luxury'),
  ('aveda',             'Aveda',             'https://www.aveda.com',            'luxury'),
  ('kevin-murphy',      'Kevin Murphy',      'https://kevinmurphy.com',          'luxury'),
  ('briogeo',           'Briogeo',           'https://briogeohair.com',          'luxury'),
  ('igk',               'IGK',               'https://igkhair.com',              'luxury'),
  ('r-and-co',          'R+Co',              'https://www.randco.com',           'luxury'),
  ('ouai',              'Ouai',              'https://theouai.com',              'luxury'),
  ('christophe-robin',  'Christophe Robin',  'https://www.christophe-robin.com', 'luxury'),
  ('sachajuan',         'Sachajuan',         'https://sachajuan.com',            'luxury'),
  ('color-wow',         'Color Wow',         'https://www.colorwowhair.com',     'luxury'),
  ('act-and-acre',      'Act+Acre',          'https://actandacre.com',           'luxury'),
  ('crown-affair',      'Crown Affair',      'https://www.crownaffair.com',      'luxury'),
  ('rahua',             'Rahua',             'https://rahua.com',                'luxury'),
  ('amika',             'Amika',             'https://www.loveamika.com',        'everyday'),
  ('verb',              'Verb',              'https://www.verbproducts.com',     'everyday'),
  ('odele',             'Odele',             'https://www.odelebeauty.com',      'everyday'),
  ('playa',             'Playa',             'https://www.playa.com',            'everyday'),
  ('pattern-beauty',    'Pattern Beauty',    'https://patternbeauty.com',        'everyday'),
  ('mielle-organics',   'Mielle Organics',   'https://mielleorganics.com',       'everyday'),
  ('sheamoisture',      'SheaMoisture',      'https://www.sheamoisture.com',     'everyday'),
  ('camille-rose',      'Camille Rose',      'https://www.camillerose.com',      'everyday'),
  ('adwoa-beauty',      'Adwoa Beauty',      'https://adwoabeauty.com',          'everyday'),
  ('cantu',             'Cantu',             'https://www.cantubeauty.com',      'everyday')
on conflict (slug) do update set
  name        = excluded.name,
  website_url = excluded.website_url,
  tier        = excluded.tier;
