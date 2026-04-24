-- =============================================================================
-- Second brand-seed wave — 44 new brands covering texture-specific lines
-- (curly / coily / wavy / protective), additional prestige / salon labels,
-- and mainstream drugstore staples (Pantene, Dove, L'Oréal Paris, …). The
-- staples carry real catalogs but their brand sites are marketing pages
-- without INCI on individual PDPs; the scraper will discover which ones
-- surface ingredients and which come back `missing`.
--
-- Idempotent on slug — re-running refreshes name / website_url / tier.
-- =============================================================================

insert into brands (slug, name, website_url, tier) values
  -- Texture-specific
  ('miss-jessies',          'Miss Jessie''s',         'https://missjessies.com',                     'everyday'),
  ('devacurl',              'DevaCurl',               'https://www.devacurl.com',                    'everyday'),
  ('kinky-curly',           'Kinky-Curly',            'https://kinky-curly.com',                     'everyday'),
  ('tgin',                  'TGIN',                   'https://tginonline.com',                      'everyday'),
  ('design-essentials',     'Design Essentials',      'https://designessentials.com',                'everyday'),
  ('aunt-jackies',          'Aunt Jackie''s',         'https://auntjackiescurlsandcoils.com',        'everyday'),
  ('the-mane-choice',       'The Mane Choice',        'https://themanechoice.com',                   'everyday'),
  ('eden-bodyworks',        'Eden BodyWorks',         'https://edenbodyworks.com',                   'everyday'),
  ('as-i-am',               'As I Am',                'https://asiamnaturally.com',                  'everyday'),
  ('uncle-funkys-daughter', 'Uncle Funky''s Daughter','https://unclefunkysdaughter.com',             'everyday'),
  ('ouidad',                'Ouidad',                 'https://ouidad.com',                          'everyday'),
  ('carols-daughter',       'Carol''s Daughter',      'https://carolsdaughter.com',                  'everyday'),
  ('jane-carter-solution',  'Jane Carter Solution',   'https://janecarter.com',                      'everyday'),
  ('oyin-handmade',         'Oyin Handmade',          'https://oyinhandmade.com',                    'everyday'),
  ('curlsmith',             'Curlsmith',              'https://curlsmith.com',                       'everyday'),
  ('alikay-naturals',       'Alikay Naturals',        'https://alikaynaturals.com',                  'everyday'),
  ('bread-beauty-supply',   'Bread Beauty Supply',    'https://breadbeautysupply.com',               'luxury'),
  ('flora-and-curl',        'Flora & Curl',           'https://floraandcurl.com',                    'luxury'),
  ('dizziak',               'Dizziak',                'https://dizziak.com',                         'luxury'),
  -- Luxury additions
  ('philip-b',              'Philip B',               'https://philipb.com',                         'luxury'),
  ('leonor-greyl',          'Leonor Greyl',           'https://www.leonorgreyl-usa.com',             'luxury'),
  ('shu-uemura-art-of-hair','Shu Uemura Art of Hair', 'https://www.shuuemuraartofhair-usa.com',      'luxury'),
  ('iles-formula',          'Iles Formula',           'https://ilesformula.com',                     'luxury'),
  ('phyto',                 'Phyto',                  'https://www.phyto-usa.com',                   'luxury'),
  ('rene-furterer',         'René Furterer',          'https://www.renefurtererusa.com',             'luxury'),
  ('prose',                 'Prose',                  'https://prose.com',                           'luxury'),
  ('gisou',                 'Gisou',                  'https://gisou.com',                           'luxury'),
  ('redken',                'Redken',                 'https://www.redken.com',                      'luxury'),
  ('pureology',             'Pureology',              'https://www.pureology.com',                   'luxury'),
  ('alterna-haircare',      'Alterna Haircare',       'https://www.alternahaircare.com',             'luxury'),
  ('eleven-australia',      'Eleven Australia',       'https://elevenaustralia.com',                 'luxury'),
  ('original-mineral',      'Original & Mineral',     'https://originalmineral.com',                 'luxury'),
  ('klorane',               'Klorane',                'https://www.klorane.com',                     'luxury'),
  ('mizani',                'Mizani',                 'https://www.mizani.com',                      'luxury'),
  -- Mainstream staples
  ('garnier',               'Garnier',                'https://www.garnierusa.com',                  'everyday'),
  ('pantene',               'Pantene',                'https://pantene.com',                         'everyday'),
  ('dove',                  'Dove',                   'https://www.dove.com',                        'everyday'),
  ('herbal-essences',       'Herbal Essences',        'https://herbalessences.com',                  'everyday'),
  ('aussie',                'Aussie',                 'https://www.aussie.com',                      'everyday'),
  ('tresemme',              'Tresemmé',               'https://www.tresemme.com',                    'everyday'),
  ('loreal-paris',          'L''Oréal Paris',         'https://www.lorealparisusa.com',              'everyday'),
  ('john-frieda',           'John Frieda',            'https://www.johnfrieda.com',                  'everyday'),
  ('ogx',                   'OGX',                    'https://ogxbeauty.com',                       'everyday'),
  ('suave',                 'Suave',                  'https://www.suave.com',                       'everyday')
on conflict (slug) do update set
  name        = excluded.name,
  website_url = excluded.website_url,
  tier        = excluded.tier;
