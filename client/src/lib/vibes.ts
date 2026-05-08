/**
 * vibes.ts — Add new music + GIF pairs here. Nothing else needs changing.
 *
 * HOW TO ADD A NEW VIBE:
 *   1. Drop your .mp3 into client/music/
 *   2. import myTrack from '../../music/mytrack.mp3'  (at top of this file)
 *   3. Add an entry to VIBES below: { music, musicStartAt, gifPostId, gifAspectRatio }
 *
 * To find a Tenor GIF's postId + aspectRatio:
 *   - Go to tenor.com, find a GIF, click Share → Embed
 *   - Copy data-postid and data-aspect-ratio from the embed code
 */

import blingMusic from '../../music/bling.mp3'
import tameMusic from '../../music/tame.mp3'
import apMusic from '../../music/AP.mp3'
import dkMusic from '../../music/DK.mp3'
import bounceMusic from '../../music/bounce.mp3'

export interface Vibe {
  music: string   // imported mp3 URL (via Vite)
  musicStartAt: number   // seek position in seconds (e.g. 63 = 1:03)
  musicVolume: number   // 0.0 – 1.0
  gifPostId: string   // Tenor data-postid
  gifAspectRatio: string   // Tenor data-aspect-ratio
  label: string   // short name shown in UI (e.g. "Mashle")
}

// ─── ✏️  ADD / REMOVE VIBES HERE ─────────────────────────────────────────────
export const VIBES: Vibe[] = [
  {
    label: 'Mashle',
    music: blingMusic,
    musicStartAt: 14,        // 1:03
    musicVolume: 0.5,
    gifPostId: '9745779996362916675',
    gifAspectRatio: '2.44118',
  },
  {
    label: 'Tame',
    music: tameMusic,
    musicStartAt: 0,
    musicVolume: 0.45,
    gifPostId: '25983175',    // Dancing Cat rainbow
    gifAspectRatio: '1.07023',
  },
  {
    label: 'AP',
    music: apMusic,
    musicStartAt: 0,
    musicVolume: 0.5,
    gifPostId: '22867099',   // replace with real Tenor ID
    gifAspectRatio: '2.35294',
  },
  {
    label: 'DK',
    music: dkMusic,
    musicStartAt: 0,
    musicVolume: 0.5,
    gifPostId: '5514765',   // replace with real Tenor ID
    gifAspectRatio: '1.33333',
  },
  {
    label: 'Bounce',
    music: bounceMusic,
    musicStartAt: 0,
    musicVolume: 0.5,
    gifPostId: '21854873',   // replace with real Tenor ID
    gifAspectRatio: '1.0',
  },
]
// ─────────────────────────────────────────────────────────────────────────────

/** Pick a random vibe from the list. */
export function randomVibe(): Vibe {
  return VIBES[Math.floor(Math.random() * VIBES.length)]
}

/** Pick the next vibe in sequence (wraps around), excluding the current one if possible. */
export function nextVibe(current: Vibe): Vibe {
  if (VIBES.length === 1) return current
  const idx = VIBES.indexOf(current)
  // Pick random from remaining
  const others = VIBES.filter((_, i) => i !== idx)
  return others[Math.floor(Math.random() * others.length)]
}
