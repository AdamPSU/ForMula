-- =============================================================================
-- Third brand-seed wave — 40 brands (10 per hair type) to fill coverage gaps
-- around straight, wavy, curly, and kinky/coily textures. Surfaced via Tavily
-- research; URLs hand-filled since research-mode returns blank URLs for
-- homepage claims. Idempotent on slug.
-- =============================================================================

insert into brands (slug, name, website_url, tier) values
  -- Straight / smoothing / professional
  ('drybar',                 'Drybar',                      'https://www.thedrybarshop.com',    'everyday'),
  ('nexxus',                 'Nexxus',                      'https://www.nexxus.com',           'everyday'),
  ('biosilk',                'BioSilk',                     'https://biosilkhair.com',          'everyday'),
  ('paul-mitchell',          'Paul Mitchell',               'https://www.paulmitchell.com',     'everyday'),
  ('joico',                  'Joico',                       'https://www.joico.com',            'luxury'),
  ('bed-head',               'Bed Head by TIGI',            'https://www.bedhead.com',          'everyday'),
  ('kristin-ess',            'Kristin Ess',                 'https://www.kristinesshair.com',   'everyday'),
  ('lanza',                  'L''ANZA',                     'https://www.lanza.com',            'luxury'),
  ('wella-professionals',    'Wella Professionals',         'https://www.wella.com',            'luxury'),
  ('kenra-professional',     'Kenra Professional',          'https://www.kenraprofessional.com','everyday'),
  -- Wavy / 2A-2C
  ('controlled-chaos',       'Controlled Chaos',            'https://controlledchaoshair.com',  'everyday'),
  ('ag-hair',                'AG Hair',                     'https://aghair.com',               'everyday'),
  ('innersense',             'Innersense Organic Beauty',   'https://innersensebeauty.com',     'luxury'),
  ('cake-beauty',            'Cake Beauty',                 'https://cakebeauty.com',           'everyday'),
  ('bondi-boost',            'BondiBoost',                  'https://bondiboost.com',           'luxury'),
  ('kitsch',                 'Kitsch',                      'https://mykitsch.com',             'everyday'),
  ('umberto-giannini',       'Umberto Giannini',            'https://www.umbertogiannini.com',  'everyday'),
  ('boucleme',               'Bouclème',                    'https://boucleme.com',             'luxury'),
  ('not-your-mothers',       'Not Your Mother''s',          'https://notyourmothers.com',       'everyday'),
  ('ceremonia',              'Ceremonia',                   'https://www.ceremonia.com',        'luxury'),
  -- Curly / 3A-3C
  ('bounce-curl',            'Bounce Curl',                 'https://bouncecurl.com',           'everyday'),
  ('jessicurl',              'Jessicurl',                   'https://jessicurl.com',            'everyday'),
  ('righteous-roots',        'Righteous Roots',             'https://shoprighteousroots.com',   'everyday'),
  ('rizos-curls',            'Rizos Curls',                 'https://www.rizoscurls.com',       'everyday'),
  ('moptop',                 'MopTop',                      'https://moptophair.com',           'everyday'),
  ('giovanni',               'Giovanni',                    'https://www.giovannicosmetics.com','everyday'),
  ('avalon-organics',        'Avalon Organics',             'https://www.avalonorganics.com',   'everyday'),
  ('100-percent-pure',       '100% Pure',                   'https://www.100percentpure.com',   'luxury'),
  ('hairstory',              'Hairstory',                   'https://hairstory.com',            'luxury'),
  ('ecoslay',                'Ecoslay',                     'https://ecoslay.com',              'everyday'),
  -- Kinky / coily / 4A-4C
  ('melanin-haircare',       'Melanin Haircare',            'https://melaninhaircare.com',      'luxury'),
  ('jamaican-mango-and-lime','Jamaican Mango & Lime',       'https://jmlbeauty.com',            'everyday'),
  ('ors',                    'ORS',                         'https://orshaircare.com',          'everyday'),
  ('dark-and-lovely',        'Dark and Lovely',             'https://www.darkandlovely.com',    'everyday'),
  ('soultanicals',           'Soultanicals',                'https://soultanicals.com',         'everyday'),
  ('naturalicious',          'Naturalicious',               'https://naturalicious.com',        'everyday'),
  ('creme-of-nature',        'Creme of Nature',             'https://www.cremeofnature.com',    'everyday'),
  ('alodia',                 'Alodia Haircare',             'https://alodiahaircare.com',       'luxury'),
  ('qhemet-biologics',       'Qhemet Biologics',            'https://qhemetbiologics.com',      'everyday'),
  ('taliah-waajid',          'Taliah Waajid',               'https://taliahwaajid.com',         'everyday')
on conflict (slug) do update set
  name        = excluded.name,
  website_url = excluded.website_url,
  tier        = excluded.tier;
