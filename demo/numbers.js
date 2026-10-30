/* ==========================================================================
   HEADLINE NUMBERS. Every figure in the story and the numbers panel comes
   from this block. Live mode shows only what the models just returned.

   Edit figures here, and nowhere else. Search for PENDING to find what will
   change when a run finishes. Nothing here is estimated for the demo.
   Do not add numbers from the old ChatML runs.
   ========================================================================== */
window.HALALA_NUMBERS = {
  // Questions per form on every development table.
  perForm: 45,

  // ALLaM 7B by form, current instruction. A comparison in comparisons.json names these rows by key, so a new
  // comparison needs a row here and nothing in the page.
  // right: runs/local_gemma/prompt_eval.md, row "Always large, raw question, current instruction".
  //   The last row is runs/local/rewrite_eval.md, row "Rules + word list".
  // tokensPerRight: PROJECT_PAGE.md, recomputed from cache/calls.sqlite on 2026-10-30
  //   (53.4, 48.6, 52.4, 47.5, 292.7, and 2118 tokens / 31 = 68.3).
  // strong: named on the result step as already strong. tone: colours the row in the numbers panel.
  forms: [
    { key: "en", name: "English", right: 42, tokensPerRight: 53 },
    { key: "msa", name: "Formal Arabic", shortName: "formal Arabic", strong: true, right: 44, tokensPerRight: 49 },
    { key: "najdi", name: "Najdi", shortName: "Najdi", strong: true, right: 40, tokensPerRight: 52 },
    { key: "mixed", name: "Mixed Arabic-English", shortName: "mixed", strong: true, right: 45, tokensPerRight: 47 },
    { key: "arabizi", name: "Arabizi, as typed", tone: "gap", right: 9, tokensPerRight: 293 },
    { key: "arabizi-rewritten", name: "Arabizi, rewritten", tone: "fixed", right: 31, tokensPerRight: 68 },
  ],

  // What detect_variant in halala/features.py can return, as live mode names it.
  detected: {
    en: "English",
    msa: "Formal Arabic",
    dialect: "Arabic dialect",
    arabizi: "Arabizi",
    mixed: "Mixed Arabic-English",
  },

  // Display names for the model names in the configs. Any other model shows its config name.
  modelNames: {
    "allam-7b-q4-inst": "ALLaM 7B",
    "gemma3:4b": "Gemma 3 4B",
  },

  // Why each route is taken, as live mode explains it. {small} and {large} become the model names.
  routeReasons: {
    small: "English goes to the smaller model once. It did as well as the large one in my tests, for less compute.",
    large: "Everything that isn't English goes to {large}, which is strong on Arabic.",
    fallback: "{small} gave no usable answer, so {large} answered instead.",
  },

  // Rules with no word list, the safer guide to unseen text.
  // Source: runs/local/rewrite_eval.md, row "Rules, no word list".
  rulesOnlyRight: 24,

  // Other ways of handling Arabizi on the same questions, and what ALLaM's own rewrite reached.
  // Source: runs/local/rewrite_eval.md, row count and rows "Large model rewrite" and "Large model rewrite + examples".
  rewriteArms: 12,
  allamRewriteRight: 15,
  allamRewriteExamplesRight: 26,

  // Entries in LEXICON. Source: halala/arabizi_lexicon.py.
  lexiconWords: 125,

  // English answered by Gemma 3 4B against ALLaM 7B.
  // Source: runs/local_gemma/prompt_eval.md, "Correct by form", en column.
  gemmaEnglishRight: 43,

  // All 225 development questions. costPct is estimated compute per right answer, always ALLaM = 100.
  // Always ALLaM and Halala: runs/local_gemma/prompt_eval.md. ALLaM + rewrite: PLAN.md line 101.
  // PENDING prompt-eval: update Halala's row (and add the always-ALLaM row on the same instruction).
  designs: [
    { name: "Always ALLaM", right: 180, costPct: 100 },
    { name: "ALLaM + rewrite", right: 202, costPct: 85 },
    { name: "Halala", right: 203, costPct: 76 }, // PENDING prompt-eval
  ],
  questionsTotal: 225,

  // The complex design I dropped, on the 30 dev-test questions. slowSeconds is p95 latency.
  // Source: runs/local_gemma/results.md, top table, rows "Full pipeline" and "Halala".
  thrownOut: {
    questions: 30,
    full: { rightPct: 90, costPct: 77, slowSeconds: 9.4 },
    simple: { rightPct: 90, costPct: 76, slowSeconds: 3.5 },
  },

  // Dataset shape. Source: PROJECT_PAGE.md, "How it was tested".
  questions: 56,
  devQuestions: 45,
  lockedQuestions: 11,

  // PENDING sealed run: replace null with one sentence, for example
  // "On those 11 questions in five forms, Halala got X of 55 at Y% of the cost."
  sealedResult: null,

  // PENDING audit: replace null with one sentence from runs/local_gemma/dialect_audit.md.
  // While it is null, nothing about the public benchmark is shown.
  auditResult: null,
};
