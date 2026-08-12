/**
 * Phase 3 quality fix — pure-function unit tests.
 *
 * Tests the brief cache key logic and the parseBriefSections formatter
 * that were added/changed in this fix.
 *
 * Run with:
 *   node frontend/tests/phase3_quality_fixes.test.mjs
 *
 * No test framework required — uses Node.js built-in assert.
 */

import assert from 'node:assert/strict';

// ---------------------------------------------------------------------------
// Inline the functions under test (mirrors frontend/src/hooks/useMissionAI.ts
// and frontend/src/components/ai/MissionAIPanel.tsx logic exactly).
// ---------------------------------------------------------------------------

/** Produce a stable string key for a set of overrides. */
function overridesKey(overrides) {
  if (!overrides) return '';
  const active = Object.entries(overrides)
    .filter(([, v]) => v !== null && v !== undefined)
    .sort(([a], [b]) => a.localeCompare(b));
  return active.length === 0 ? '' : JSON.stringify(active);
}

/** Full cache key: profile + simulation context. */
function briefCacheKey(profile, overrides) {
  return `${profile}::${overridesKey(overrides)}`;
}

/**
 * Matches the parseBriefSections logic in MissionAIPanel.tsx.
 */
function parseBriefSections(text) {
  const HEADERS = ['READINESS', 'PRIMARY DRIVERS', 'MONITOR', 'CONTEXT'];
  const pattern = new RegExp(`^(${HEADERS.join('|')})\\s*:?\\s*$`, 'i');

  const sections = [];
  let current = null;

  for (const raw of text.split('\n')) {
    const line = raw.trim();
    if (!line) {
      if (current) current.lines.push('');
      continue;
    }
    if (pattern.test(line)) {
      if (current) sections.push(current);
      current = { label: line.replace(/:$/, '').trim().toUpperCase(), lines: [] };
    } else {
      if (!current) current = { label: '', lines: [] };
      current.lines.push(
        line.replace(/^#{1,4}\s*/, '').replace(/\*\*/g, '').replace(/^\*\s/, '• ')
      );
    }
  }
  if (current) sections.push(current);
  return sections.filter((s) => s.lines.some((l) => l.trim().length > 0));
}

// ---------------------------------------------------------------------------
// Tests: cache key isolation
// ---------------------------------------------------------------------------

console.log('Running Phase 3 quality fix tests...\n');

// 1. Different profiles → different keys
{
  const key1 = briefCacheKey('ASTRONAUT_EVA', null);
  const key2 = briefCacheKey('ROCKET_LAUNCH', null);
  assert.notEqual(key1, key2, 'ASTRONAUT_EVA and ROCKET_LAUNCH must have different cache keys');
  console.log('✓ Different profiles produce different cache keys');
}

// 2. Same profile, no overrides → same key (cache hit)
{
  const key1 = briefCacheKey('ROCKET_LAUNCH', null);
  const key2 = briefCacheKey('ROCKET_LAUNCH', null);
  assert.equal(key1, key2, 'Same profile with no overrides must produce the same cache key');
  console.log('✓ Same profile, no overrides → same key (cache can hit)');
}

// 3. Same profile, with vs without overrides → different keys
{
  const live = briefCacheKey('ROCKET_LAUNCH', null);
  const sim = briefCacheKey('ROCKET_LAUNCH', { kp_index: 8.5 });
  assert.notEqual(live, sim, 'Live and simulated contexts must have different keys');
  console.log('✓ Live vs simulated contexts have different keys');
}

// 4. Two different simulated scenarios → different keys
{
  const sim1 = briefCacheKey('ROCKET_LAUNCH', { kp_index: 5.0 });
  const sim2 = briefCacheKey('ROCKET_LAUNCH', { kp_index: 9.0 });
  assert.notEqual(sim1, sim2, 'Different simulation values must produce different keys');
  console.log('✓ Different simulated values produce different keys');
}

// 5. All four profiles produce distinct keys
{
  const profiles = ['ROCKET_LAUNCH', 'LEO_SATELLITE', 'ASTRONAUT_EVA', 'LUNAR_MISSION'];
  const keys = profiles.map((p) => briefCacheKey(p, null));
  const unique = new Set(keys);
  assert.equal(unique.size, 4, `Expected 4 unique keys for 4 profiles, got ${unique.size}`);
  console.log('✓ All four mission profiles have unique cache keys');
}

// 6. Overrides key order stability (different insertion order, same effective overrides)
{
  const a = overridesKey({ kp_index: 5, bz_gsm_nt: -10 });
  const b = overridesKey({ bz_gsm_nt: -10, kp_index: 5 });
  assert.equal(a, b, 'Overrides key must be stable regardless of property order');
  console.log('✓ Overrides key is stable under property insertion order');
}

// 7. Null/undefined override values are ignored (not active)
{
  const a = overridesKey({ kp_index: null, bz_gsm_nt: null });
  const b = overridesKey(null);
  assert.equal(a, b, 'All-null overrides should produce same key as no overrides');
  console.log('✓ All-null overrides treated same as no overrides');
}

// ---------------------------------------------------------------------------
// Tests: parseBriefSections (Issue 5 — no raw Markdown markers rendered)
// ---------------------------------------------------------------------------

// 8. Structured sections are parsed correctly
{
  const text = `READINESS\nModerate risk.\n\nPRIMARY DRIVERS\n- Geomagnetic\n- Radiation\n\nMONITOR\n- Kp trend\n\nCONTEXT\nData complete.`;
  const sections = parseBriefSections(text);
  assert.equal(sections.length, 4, `Expected 4 sections, got ${sections.length}`);
  assert.equal(sections[0].label, 'READINESS');
  assert.equal(sections[1].label, 'PRIMARY DRIVERS');
  assert.equal(sections[2].label, 'MONITOR');
  assert.equal(sections[3].label, 'CONTEXT');
  console.log('✓ parseBriefSections parses 4 labelled sections correctly');
}

// 9. Markdown ** markers are stripped
{
  const text = `READINESS\n**Moderate** risk.\n\nPRIMARY DRIVERS\n- **Geomagnetic** factor`;
  const sections = parseBriefSections(text);
  const readinessContent = sections.find(s => s.label === 'READINESS')?.lines.join(' ') ?? '';
  assert.ok(!readinessContent.includes('**'), 'Markdown ** markers must be stripped from section lines');
  console.log('✓ Markdown ** markers are stripped from section content');
}

// 10. Markdown ## heading markers are stripped
{
  const text = `## READINESS\nModerate risk.\n\n## PRIMARY DRIVERS\n- Kp\n\n## MONITOR\n- Kp\n\n## CONTEXT\nOK.`;
  const sections = parseBriefSections(text);
  // When Granite uses ## headers, the parser should still detect sections or strip markers
  const allContent = sections.flatMap(s => s.lines).join('\n');
  assert.ok(!allContent.includes('##'), 'Markdown ## heading markers must be stripped');
  console.log('✓ Markdown ## heading markers are stripped from content');
}

// 11. Fallback: plain text without section headers is not rendered with ** markers
{
  const rawText = '**Mission Brief**\n**Primary drivers:** high Kp.';
  const sections = parseBriefSections(rawText);
  // The text will land in an unlabelled section; markers must be stripped
  const allContent = sections.flatMap(s => s.lines).join('\n');
  assert.ok(!allContent.includes('**'), 'Fallback plain text must have ** stripped');
  console.log('✓ Fallback plain text path strips ** markers');
}

// 12. Changing profile → old brief cannot show (simulated via cache key mismatch)
{
  // Simulate: user has a cached EVA brief
  const evaKey = briefCacheKey('ASTRONAUT_EVA', null);
  const rlKey = briefCacheKey('ROCKET_LAUNCH', null);
  // After switching to ROCKET_LAUNCH, the cache lookup uses rlKey — it will miss the EVA entry
  assert.notEqual(evaKey, rlKey, 'ROCKET_LAUNCH lookup key must differ from EVA — stale brief cannot appear');
  console.log('✓ Profile switch: ROCKET_LAUNCH cache key differs from ASTRONAUT_EVA → no stale brief');
}

console.log('\nAll Phase 3 quality fix tests passed.');
