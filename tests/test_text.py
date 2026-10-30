import unittest

from halala.config import ROOT
from halala.data import load_jsonl
from halala.features import detect_variant  # noqa: F401  (used by DetectVariantTest and VariantTest)
from halala.normalize import arabizi_to_arabic, for_match, for_model
from halala.scoring import extract_choice, is_correct, is_refusal, score

EXPECTED = {"en": "en", "msa": "msa", "najdi": "dialect", "arabizi": "arabizi", "mixed": "mixed"}


class NormalizeTest(unittest.TestCase):
    def test_for_model_strips_diacritics_and_tatweel_and_converts_digits(self):
        self.assertEqual(for_model("مَدْرَسَـــة ١٥"), "مدرسة 15")

    def test_for_match_folds_letter_variants_and_punctuation(self):
        self.assertEqual(for_match("أكبر إلى آخر مستشفى مدرسة؟"), "اكبر الي اخر مستشفي مدرسه")

    def test_for_match_keeps_decimal_points(self):
        self.assertEqual(for_match("3.5."), "3.5")

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


class VariantTest(unittest.TestCase):
    def test_hand_written_smoke_set(self):
        for item in load_jsonl(ROOT / "data" / "smoke_parallel.jsonl"):
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


if __name__ == "__main__":
    unittest.main()
