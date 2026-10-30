import unittest

from halala.config import ROOT
from halala.data import load_jsonl, make_synthetic_arith
from halala.features import detect_variant  # noqa: F401  (used by DetectVariantTest and VariantTest)
from halala.normalize import arabizi_kit, arabizi_to_arabic, dialect_to_formal, for_match, for_model
from halala.collect import check_rewrite, summarize_samples
from halala.models import Completion
from halala.scoring import answer_key, cluster_answers, extract_choice, is_correct, is_refusal, score

EXPECTED = {"en": "en", "msa": "msa", "najdi": "dialect", "arabizi": "arabizi", "mixed": "mixed"}


class NormalizeTest(unittest.TestCase):
    def test_for_model_strips_diacritics_and_tatweel_and_converts_digits(self):
        self.assertEqual(for_model("مَدْرَسَـــة ١٥"), "مدرسة 15")

    def test_for_match_folds_letter_variants_and_punctuation(self):
        self.assertEqual(for_match("أكبر إلى آخر مستشفى مدرسة؟"), "اكبر الي اخر مستشفي مدرسه")

    def test_for_match_keeps_decimal_points(self):
        self.assertEqual(for_match("3.5."), "3.5")

    def test_arabizi_kit_leaves_numbers_alone(self):
        out = arabizi_kit("kam ytla3 15 zayed 27?")
        self.assertIn("15", out)
        self.assertIn("27", out)
        self.assertTrue(out.endswith("؟"))
        self.assertEqual(arabizi_kit("el sa3a 8"), arabizi_kit("el sa3a") + " 8")   # "8" alone isn't the letter غ

    def test_arabizi_rules(self):
        self.assertEqual(arabizi_to_arabic("wesh"), "وش")
        self.assertEqual(arabizi_to_arabic("kam 15?"), "كم 15؟")
        self.assertEqual(arabizi_to_arabic("el ba7r"), "البحر")

    def test_arabizi_keeps_endings_prefixes_and_single_letters(self):
        nolex = lambda t: arabizi_to_arabic(t, lexicon=False)   # noqa: E731
        self.assertEqual(nolex("nakhla"), "نخلة")      # final a is ة
        self.assertEqual(nolex("watani"), "وتني")      # final i is ي
        self.assertEqual(nolex("masjid hijri"), "مسجد هجري")
        self.assertEqual(nolex("rasmiya"), "رسمية")    # final iya is ية
        self.assertEqual(nolex("feeha"), "فيها")       # final ha is ها
        self.assertEqual(nolex("3asha"), "عشة")        # but "sha" in 3asha is one letter
        self.assertEqual(nolex("yitjammad"), "يتجمد")  # doubled consonants are written once
        self.assertEqual(nolex("bil bait"), "بالبت")   # bil attaches to its word
        self.assertEqual(nolex("lil shams"), "للشمس")  # lil attaches to its word
        self.assertEqual(nolex("rihlat wa7ed"), "رهلة وحد")   # "at" before another word is ة

    def test_arabizi_word_list(self):
        self.assertEqual(arabizi_to_arabic("wesh 3asmat el sa3odiya?"), "وش عاصمة السعودية؟")
        self.assertEqual(arabizi_to_arabic("bi ay shahar?"), "بأي شهر؟")


class DialectToFormalTest(unittest.TestCase):
    def test_swaps_dialect_words_and_keeps_the_rest(self):
        self.assertEqual(dialect_to_formal("وش البحر اللي على الساحل؟"), "ما البحر الذي على الساحل؟")

    def test_keeps_an_attached_conjunction(self):
        self.assertEqual(dialect_to_formal("وليش فاللي"), "ولماذا فالذي")

    def test_phrases_go_first(self):
        self.assertEqual(dialect_to_formal("عشان كذا كم يطلع ٥"), "لذلك كم يساوي ٥")

    def test_leaves_formal_arabic_and_latin_alone(self):
        for text in ("ما عاصمة السعودية؟", "بكرة في الفيزياء", "وفصل الربيع", "Which city is it?"):
            self.assertEqual(dialect_to_formal(text), text)


class DetectVariantTest(unittest.TestCase):
    def test_one_english_word_in_an_arabic_sentence_is_mixed(self):
        # Only ~7% of the letters are Latin, so a letter-ratio rule called this pure dialect.
        self.assertEqual(detect_variant("وش الـ sea اللي على الساحل الغربي؟"), "mixed")
        self.assertEqual(detect_variant("وش أكبر planet في المجموعة الشمسية؟"), "mixed")

    def test_arabizi_without_digits(self):
        self.assertEqual(detect_variant("bi ay shahar nsoom?"), "arabizi")   # two weak markers
        self.assertEqual(detect_variant("wesh akbar kawkab?"), "arabizi")    # one strong marker
        self.assertEqual(detect_variant("el ba7r el a7mar"), "arabizi")      # digits inside words

    def test_plain_english_is_not_arabizi(self):
        self.assertEqual(detect_variant("What is the capital of Saudi Arabia?"), "en")
        self.assertEqual(detect_variant("Set the min value to 3."), "en")    # one weak marker is not enough

    def test_english_with_digits_or_marker_words_stays_english(self):
        for text in ("What is CO2?", "Who was the 3rd president?", "What does H2O stand for?",
                     "Name the 2nd largest city in the UK.", "I wish to know the capital of France.",
                     "Who founded Zain and when?"):
            with self.subTest(text=text):
                self.assertEqual(detect_variant(text), "en")

    def test_unsure_latin_text_goes_to_the_large_model_as_typed(self):
        self.assertEqual(detect_variant("mata yabda ramadan"), "mixed")
        self.assertEqual(detect_variant("Define entropy"), "mixed")
        self.assertEqual(detect_variant("H2O formula"), "mixed")

    def test_arabic_only(self):
        self.assertEqual(detect_variant("ما هي عاصمة المملكة العربية السعودية؟"), "msa")
        self.assertEqual(detect_variant("وش عاصمة السعودية؟"), "dialect")


class RewriteCheckTest(unittest.TestCase):
    """Real ALLaM 7B rewrites from the 2026-10-30 profile run."""

    def test_rejects_format_failures(self):
        self.assertEqual(check_rewrite("wesh 3omlat el sa3odiya?",
                                       "عذرا، لا أستطيع فهم ما تقصده. يرجى إعادة صياغة السؤال أو استخدام كلمات أكثر وضوحًا."),
                         "refusal")
        self.assertEqual(check_rewrite("wesh el ba7r elly 3ala el sa7el el gharbi lil sa3odiya?",
                                       "ويش البحر اللي على الساحل الغربي للسعودية؟<|im|> البحر اللي على الساحل الغربي هو البحر الأحمر."),
                         "chat token")
        self.assertEqual(check_rewrite("kam 15?", ""), "empty")
        self.assertEqual(check_rewrite("kam 15?", "kam 15?"), "not Arabic script")
        self.assertEqual(check_rewrite("kam 15?", "كم 15؟ " + "وهذا شرح طويل جدا لا علاقة له بالسؤال " * 3), "too long")

    def test_accepts_clean_rewrites(self):
        self.assertEqual(check_rewrite("wesh akbar kawkab bil majmoo3a el shamsiya?",
                                       "ويش أكبر كوكب في المجموعة الشمسية؟"), "")
        # Wrong meaning but well formed: the check can't catch this one (that's H5's job).
        self.assertEqual(check_rewrite("el osboo3 kam yom?", "الولد كم عمره؟"), "")


class VariantTest(unittest.TestCase):
    def test_hand_written_smoke_set(self):
        for item in load_jsonl(ROOT / "data" / "smoke_parallel.jsonl"):
            with self.subTest(question=item.question):
                self.assertEqual(detect_variant(item.question), EXPECTED[item.variant])

    def test_synthetic_set(self):
        for item in make_synthetic_arith(50, seed=3):
            with self.subTest(question=item.question):
                self.assertEqual(detect_variant(item.question), EXPECTED[item.variant])


class ScoringTest(unittest.TestCase):
    def test_numbers(self):
        self.assertTrue(is_correct("٤٢", ["42"]))
        self.assertTrue(is_correct("The answer is 42.", ["42"]))
        self.assertFalse(is_correct("142", ["42"]))
        self.assertFalse(is_correct("", ["42"]))

    def test_words(self):
        self.assertTrue(is_correct("riyadh", ["Riyadh"]))
        self.assertTrue(is_correct("بالرياض", ["الرياض"]))
        self.assertTrue(is_correct("الأخضر", ["أخضر"]))
        self.assertFalse(is_correct("Jeddah", ["Riyadh", "الرياض"]))

    def test_same_answer_in_different_wording_votes_together(self):
        # ALLaM's five answers to وش عاصمة السعودية؟ on 2026-10-30, all correct.
        texts = ["الرياض", "هي الرياض.", "الرياض هي عاصمة السعودية.", "الرياض", "مدينة الرياض"]
        self.assertEqual(len(set(cluster_answers(texts))), 1)
        summary = summarize_samples([Completion(t, 1, 1, 0.0) for t in texts])
        self.assertEqual(summary["agreement"], 1.0)
        self.assertEqual(summary["majority_text"], "الرياض")

    def test_different_answers_stay_apart(self):
        ids = cluster_answers(["42", "The answer is 42.", "142", "Jeddah"])
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(len({ids[0], ids[2], ids[3]}), 3)

    def test_empty_answers_never_win(self):
        summary = summarize_samples([Completion(t, 1, 1, 0.0) for t in ["", "", "", "الرياض", "Riyadh"]])
        self.assertEqual(summary["majority_text"], "")
        self.assertEqual(summary["agreement"], 0.0)

    def test_refusals(self):
        self.assertTrue(is_refusal("عذرا، لا أستطيع تقديم معلومات عن العائلة المالكة السعودية."))   # ALLaM, 2026-10-30
        self.assertTrue(is_refusal("I'm sorry, I can't help with that."))
        self.assertFalse(is_refusal("الرياض"))
        self.assertFalse(is_refusal("فلاسفة اليونان"))   # contains the letters of آسف, but isn't a refusal

    def test_multiple_choice(self):
        choices = ["الرياض", "جدة", "مكة", "الدمام"]
        self.assertEqual(extract_choice("A", choices), "A")
        self.assertEqual(extract_choice("The answer is C.", choices), "C")
        self.assertEqual(extract_choice("الخيار ب", choices), "B")
        self.assertEqual(extract_choice("الجواب: د", choices), "D")
        self.assertEqual(extract_choice("الرياض هي العاصمة", choices), "A")   # option text, not a letter
        self.assertEqual(extract_choice("E", choices), "")                    # only four options
        self.assertEqual(extract_choice("Answer", choices), "")
        self.assertTrue(score("B", ["B"], choices))
        self.assertFalse(score("C", ["B"], choices))
        self.assertEqual(cluster_answers(["A", "A.", "الخيار أ", "B"], choices), [0, 0, 0, 1])

    def test_answer_key_for_voting(self):
        self.assertEqual(answer_key("The answer is ٤٢."), "42")
        self.assertEqual(answer_key("42"), "42")
        self.assertEqual(answer_key("الرياض."), "الرياض")


if __name__ == "__main__":
    unittest.main()
