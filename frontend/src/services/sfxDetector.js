import sfxCatalog from '../data/sfx_catalog.json' with { type: 'json' };

/**
 * SFX Detection Service
 *
 * Detects sound effect-worthy phrases in narrative text using:
 * 1. Aho-Corasick trie for catalog phrase matching
 * 2. Regex templates for patterns
 * 3. Onomatopoeia detection
 * 4. Scoring and overlap resolution
 */

// Regex templates for various SFX categories
const REGEX_TEMPLATES = {
  impacts: /\b(door|gate|window|chest|portcullis|hatch|table|cage|lever)\b.{0,10}\b(slam|bang|crash|shut|close|flip|pull|click)s?\b/gi,
  weather: /\b(thunderclap|thunder|lightning|rain|storm|gale|howl|wind|snow|hail|earthquake|blizzard|tornado)s?\b/gi,
  magic: /\b(crackle|flare|burst|whoosh|arcane|chant|incantation|spell|magic|glow|portal|teleport|fireball|summon)s?\b/gi,
  creatures: /\b(roar|howl|hiss|screech|snarl|bellow|growl|chirp|neigh|squeak|croak|moan)s?\b/gi,
  ambience: /\b(footsteps|stomp|clank|clink|rustle|creak|drip|echo|whisper|knock|tick)s?\b/gi,
  combat: /\b(slash|strike|parry|clang|clash|hit|pierce|thud|clatter|swing|stab|thrust|block|draw)s?\b/gi,
};

// Build onomatopoeia regex from catalog
const buildOnomatopoeiaRegex = () => {
  const words = sfxCatalog.onomatopoeia.join('|');
  return new RegExp(`\\b(${words})\\b`, 'gi');
};

const ONOMATOPOEIA_REGEX = buildOnomatopoeiaRegex();

/**
 * Simple Aho-Corasick-like Trie implementation
 */
class TrieNode {
  constructor() {
    this.children = new Map();
    this.output = []; // Store catalog entries that end at this node
  }
}

class AhoCorasickTrie {
  constructor() {
    this.root = new TrieNode();
  }

  /**
   * Add a pattern to the trie
   * @param {string} pattern - The trigger phrase
   * @param {Object} entry - The catalog entry
   */
  addPattern(pattern, entry) {
    const normalized = pattern.toLowerCase();
    let node = this.root;

    for (const char of normalized) {
      if (!node.children.has(char)) {
        node.children.set(char, new TrieNode());
      }
      node = node.children.get(char);
    }

    node.output.push({ pattern, entry });
  }

  /**
   * Search for all patterns in text
   * @param {string} text - The text to search
   * @returns {Array} Array of matches with positions
   */
  search(text) {
    const matches = [];
    const normalized = text.toLowerCase();

    // For each starting position in text
    for (let i = 0; i < normalized.length; i++) {
      let node = this.root;
      let j = i;

      // Try to match as long as possible from this position
      while (j < normalized.length && node.children.has(normalized[j])) {
        node = node.children.get(normalized[j]);
        j++;

        // If this node has outputs, we found matches
        if (node.output.length > 0) {
          for (const { pattern, entry } of node.output) {
            matches.push({
              phrase: text.substring(i, j), // Original case text
              startIdx: i,
              endIdx: j,
              sfxId: entry.id,
              priority: entry.priority,
              category: entry.category,
              matchType: 'catalog',
            });
          }
        }
      }
    }

    return matches;
  }
}

/**
 * Build quick lookup from synonym -> canonical target
 */
const buildSynonymLookup = () => {
  const lookup = new Map();
  for (const [target, synonyms] of Object.entries(sfxCatalog.synonyms)) {
    lookup.set(target.toLowerCase(), target.toLowerCase());
    for (const synonym of synonyms) {
      lookup.set(synonym.toLowerCase(), target.toLowerCase());
    }
  }
  return lookup;
};

const SYNONYM_LOOKUP = buildSynonymLookup();
const WORD_REGEX = /\b([A-Za-z][\w'-]*)\b/g;

/**
 * Normalize text with synonyms while preserving mapping back to original chars.
 */
const normalizeTextWithMap = (text) => {
  if (!text) {
    return { normalizedText: '', normIndexMap: [], normMetaMap: [] };
  }

  let normalizedText = '';
  const normIndexMap = [];
  const normMetaMap = [];
  let lastIndex = 0;
  let match;

  while ((match = WORD_REGEX.exec(text)) !== null) {
    const { index } = match;
    const word = match[0];

    if (index > lastIndex) {
      const chunk = text.slice(lastIndex, index);
      normalizedText += chunk.toLowerCase();
      for (let i = 0; i < chunk.length; i += 1) {
        const origIndex = lastIndex + i;
        normIndexMap.push(origIndex);
        normMetaMap.push({ origStart: origIndex, origEnd: origIndex + 1 });
      }
    }

    const lowerWord = word.toLowerCase();
    const rawReplacement = SYNONYM_LOOKUP.get(lowerWord);
    const replacement = (() => {
      if (!rawReplacement || rawReplacement === lowerWord) {
        return lowerWord;
      }
      // Avoid collapsing specific long words into shorter roots (e.g., thunderclap -> thunder)
      const replacementIsSubstring = lowerWord.includes(rawReplacement);
      if (replacementIsSubstring && lowerWord.length > rawReplacement.length + 2) {
        return lowerWord;
      }
      return rawReplacement;
    })();

    normalizedText += replacement;
    for (let i = 0; i < replacement.length; i += 1) {
      const mappedIndex = index + Math.min(i, word.length - 1);
      normIndexMap.push(mappedIndex);
      normMetaMap.push({ origStart: index, origEnd: index + word.length });
    }

    lastIndex = index + word.length;
  }

  if (lastIndex < text.length) {
    const chunk = text.slice(lastIndex);
    normalizedText += chunk.toLowerCase();
    for (let i = 0; i < chunk.length; i += 1) {
      const origIndex = lastIndex + i;
      normIndexMap.push(origIndex);
      normMetaMap.push({ origStart: origIndex, origEnd: origIndex + 1 });
    }
  }

  return { normalizedText, normIndexMap, normMetaMap };
};

const normalizeForMatching = (text) => normalizeTextWithMap(text).normalizedText;

/**
 * Build trie from catalog (normalized triggers)
 */
const buildCatalogTrie = () => {
  const trie = new AhoCorasickTrie();

  for (const entry of sfxCatalog.entries) {
    for (const trigger of entry.triggers) {
      const normalizedTrigger = normalizeForMatching(trigger);
      trie.addPattern(normalizedTrigger, entry);
    }
  }

  return trie;
};

// Build trie once on module load
const catalogTrie = buildCatalogTrie();

/**
 * Find matches using regex templates
 * @param {string} text - The text to search
 * @returns {Array} Array of matches
 */
const findRegexMatches = (text) => {
  const matches = [];

  for (const [category, regex] of Object.entries(REGEX_TEMPLATES)) {
    // Reset regex state
    regex.lastIndex = 0;

    let match;
    while ((match = regex.exec(text)) !== null) {
      matches.push({
        phrase: match[0],
        startIdx: match.index,
        endIdx: match.index + match[0].length,
        sfxId: null,
        priority: 5, // Default priority for regex matches
        category,
        matchType: 'regex',
      });
    }
  }

  return matches;
};

/**
 * Find onomatopoeia matches
 * @param {string} text - The text to search
 * @returns {Array} Array of matches
 */
const findOnomatopoeiaMatches = (text) => {
  const matches = [];
  ONOMATOPOEIA_REGEX.lastIndex = 0;

  let match;
  while ((match = ONOMATOPOEIA_REGEX.exec(text)) !== null) {
    matches.push({
      phrase: match[0],
      startIdx: match.index,
      endIdx: match.index + match[0].length,
      sfxId: null,
      priority: 4, // Default priority for onomatopoeia
      category: 'onomatopoeia',
      matchType: 'onomatopoeia',
    });
  }

  return matches;
};

/**
 * Calculate score for a match
 * @param {Object} match - The match object
 * @returns {number} The calculated score
 */
const calculateScore = (match) => {
  let score = match.priority;

  // Bonus for catalog matches
  if (match.matchType === 'catalog') {
    score += 5;
  }

  // Bonus for phrase length (up to 3 points)
  const lengthBonus = Math.min(match.phrase.length / 10, 3);
  score += lengthBonus;

  // Check for noun-verb combination (simple heuristic)
  const hasSpace = match.phrase.includes(' ');
  if (hasSpace) {
    score += 3;
  }

  return score;
};

/**
 * Check if two matches overlap
 * @param {Object} match1 - First match
 * @param {Object} match2 - Second match
 * @returns {boolean} True if they overlap
 */
const matchesOverlap = (match1, match2) => {
  return !(match1.endIdx <= match2.startIdx || match2.endIdx <= match1.startIdx);
};

/**
 * Resolve overlapping matches by selecting highest priority/longest
 * @param {Array} matches - Array of all matches
 * @returns {Array} Array of non-overlapping matches
 */
const resolveOverlaps = (matches) => {
  if (matches.length === 0) {
    return [];
  }

  // Sort by score DESC, then length DESC
  const sorted = [...matches].sort((a, b) => {
    const scoreDiff = b.score - a.score;
    if (scoreDiff !== 0) {
      return scoreDiff;
    }
    return b.phrase.length - a.phrase.length;
  });

  const selected = [];
  const usedPositions = new Set();

  for (const match of sorted) {
    // Check if this match overlaps with any already selected
    let hasOverlap = false;
    for (let i = match.startIdx; i < match.endIdx; i++) {
      if (usedPositions.has(i)) {
        hasOverlap = true;
        break;
      }
    }

    if (!hasOverlap) {
      selected.push(match);
      // Mark positions as used
      for (let i = match.startIdx; i < match.endIdx; i++) {
        usedPositions.add(i);
      }
    }
  }

  // Sort selected matches by position in text
  return selected.sort((a, b) => a.startIdx - b.startIdx);
};

/**
 * Strip excluded content while preserving a map back to original positions.
 */
const stripExcludedContentWithMap = (text) => {
  if (!text || typeof text !== 'string') {
    return { cleanText: '', indexMap: [] };
  }

  const exclusions = [];
  const exclusionRegex = /```[\s\S]*?```|\(\(OOC:.*?\)\)/gi;
  let match;
  while ((match = exclusionRegex.exec(text)) !== null) {
    exclusions.push({ start: match.index, end: match.index + match[0].length });
  }

  let cursor = 0;
  const cleanChars = [];
  const indexMap = [];

  for (const exclusion of exclusions) {
    while (cursor < exclusion.start) {
      cleanChars.push(text[cursor]);
      indexMap.push(cursor);
      cursor += 1;
    }
    cursor = exclusion.end;
  }

  while (cursor < text.length) {
    cleanChars.push(text[cursor]);
    indexMap.push(cursor);
    cursor += 1;
  }

  return { cleanText: cleanChars.join(''), indexMap };
};

/**
 * Main detection function
 * @param {string} text - The narrative text to analyze
 * @returns {Array} Array of detected SFX phrases with metadata
 */
export const detectSFXPhrases = (text, { maxMatches = 10 } = {}) => {
  if (!text || typeof text !== 'string') {
    return [];
  }

  const { cleanText, indexMap } = stripExcludedContentWithMap(text);
  if (!cleanText) {
    return [];
  }

  const { normalizedText, normIndexMap, normMetaMap } = normalizeTextWithMap(cleanText);

  // Stage 1: Catalog matching with trie on normalized text
  const catalogMatches = catalogTrie.search(normalizedText);

  // Stage 2: Regex template matching
  const regexMatches = findRegexMatches(normalizedText);

  // Stage 3: Onomatopoeia detection
  const onomatopoeiaMatches = findOnomatopoeiaMatches(normalizedText);

  const mapNormalizedRangeToOriginal = (startIdx, endIdx) => {
    if (normIndexMap.length === 0 || normMetaMap.length === 0) {
      return {
        originalStart: startIdx,
        originalEnd: endIdx,
      };
    }

    const spanMeta = normMetaMap.slice(startIdx, Math.max(endIdx, startIdx + 1));

    const cleanStart = spanMeta.reduce(
      (min, meta) => Math.min(min, meta.origStart ?? Number.MAX_SAFE_INTEGER),
      Number.MAX_SAFE_INTEGER,
    );
    const cleanEnd = spanMeta.reduce(
      (max, meta) => Math.max(max, meta.origEnd ?? 0),
      0,
    );

    const originalStart = indexMap[cleanStart] ?? cleanStart;
    const originalEnd = (cleanEnd > 0 && indexMap[cleanEnd - 1] !== undefined)
      ? (indexMap[cleanEnd - 1] + 1)
      : originalStart;

    return { originalStart, originalEnd };
  };

  const mapMatches = (matches) => matches.map((match) => {
    const { originalStart, originalEnd } = mapNormalizedRangeToOriginal(
      match.startIdx,
      match.endIdx,
    );

    const phrase = text.slice(originalStart, originalEnd);

    return {
      ...match,
      phrase,
      startIdx: originalStart,
      endIdx: originalEnd,
    };
  });

  // Combine all matches and map them back to original positions
  const allMatches = [
    ...mapMatches(catalogMatches),
    ...mapMatches(regexMatches),
    ...mapMatches(onomatopoeiaMatches),
  ];

  // Calculate scores using original phrase lengths
  const scoredMatches = allMatches.map(match => ({
    ...match,
    score: calculateScore(match),
  }));

  // Filter by minimum score threshold
  const SCORE_THRESHOLD = 6;
  const qualifyingMatches = scoredMatches.filter(m => m.score >= SCORE_THRESHOLD);

  // Resolve overlaps
  const resolvedMatches = resolveOverlaps(qualifyingMatches);

  // Take highest-scoring matches, then order by position for rendering
  const prioritized = [...resolvedMatches]
    .sort((a, b) => {
      const scoreDiff = b.score - a.score;
      if (scoreDiff !== 0) return scoreDiff;
      return b.phrase.length - a.phrase.length;
    })
    .slice(0, maxMatches)
    .sort((a, b) => a.startIdx - b.startIdx);

  return prioritized;
};

/**
 * Get catalog entry by ID
 * @param {string} sfxId - The SFX ID
 * @returns {Object|null} The catalog entry or null
 */
export const getCatalogEntry = (sfxId) => {
  return sfxCatalog.entries.find(entry => entry.id === sfxId) || null;
};

export default {
  detectSFXPhrases,
  getCatalogEntry,
};
