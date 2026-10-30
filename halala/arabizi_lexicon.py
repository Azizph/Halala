"""Common Najdi and Gulf words for the Arabizi rewrite, for spelling that rules can't recover: which s is ص, which
vowel is long, whether a word ends in ة. Everyday vocabulary only, so it can apply to questions it hasn't seen.
A word here wins over the rules. Keys are lowercase Arabizi without "el"; the rules attach prefixes afterwards.
"""

LEXICON = {
    # question and function words
    "wesh": "وش", "wish": "وش", "esh": "ايش", "elly": "اللي", "illi": "اللي", "ally": "اللي",
    "3ala": "على", "3la": "على", "ila": "إلى", "min": "من", "fi": "في", "fee": "في", "ma3": "مع",
    "kam": "كم", "law": "لو", "lamma": "لما", "ay": "أي", "ayy": "أي", "wain": "وين", "wein": "وين",
    "laish": "ليش", "leish": "ليش", "lesh": "ليش", "mata": "متى", "keef": "كيف", "kaif": "كيف",
    "shlon": "شلون", "hatha": "هذا", "hathi": "هذي", "ana": "أنا", "enta": "أنت", "inta": "أنت",
    "enti": "أنتي", "e7na": "إحنا", "hu": "هو", "hi": "هي", "3ashan": "عشان", "3shan": "عشان",
    "bas": "بس", "wala": "ولا", "mo": "مو", "ma": "ما", "feeh": "فيه", "feeha": "فيها",
    # verbs
    "abi": "أبي", "abgha": "أبغى", "tabi": "تبي", "yabi": "يبي", "ytla3": "يطلع", "yetla3": "يطلع",
    "tetla3": "تطلع", "yseer": "يصير", "tseer": "تصير", "aroo7": "أروح", "troo7": "تروح", "agool": "أقول",
    # time
    "yom": "يوم", "youm": "يوم", "sana": "سنة", "shahar": "شهر", "shahr": "شهر", "osboo3": "أسبوع",
    "usboo3": "أسبوع", "sa3a": "ساعة", "dagiga": "دقيقة", "bukra": "بكرة", "ams": "أمس", "al7een": "الحين",
    "hal7een": "الحين", "fasl": "فصل",
    # places and geography
    "madina": "مدينة", "dawla": "دولة", "balad": "بلد", "sa3odiya": "سعودية", "3asma": "عاصمة",
    "3asmat": "عاصمة", "ba7r": "بحر", "jabal": "جبل", "sa7ra": "صحراء", "3alam": "عالم", "sa7el": "ساحل",
    "sharg": "شرق", "gharb": "غرب", "sharqiya": "شرقية", "gharbi": "غربي", "masr": "مصر",
    # common nouns
    "esm": "اسم", "ism": "اسم", "lugha": "لغة", "3adad": "عدد", "riyal": "ريال", "halala": "هللة",
    "3omla": "عملة", "3omlat": "عملة", "sayyara": "سيارة", "moya": "موية", "koora": "كورة", "salah": "صلاة",
    "salat": "صلاة", "shams": "شمس", "gamar": "قمر", "7ayawan": "حيوان", "akl": "أكل", "bait": "بيت",
    "beit": "بيت", "nas": "ناس",
    # adjectives and comparatives
    "zain": "زين", "mara": "مرة", "7eil": "حيل", "kabeer": "كبير", "sagheer": "صغير", "akbar": "أكبر",
    "asghar": "أصغر", "awwal": "أول", "akher": "آخر", "a3la": "أعلى", "asra3": "أسرع", "a7ar": "أحر",
    "a7san": "أحسن", "agrab": "أقرب", "ab3ad": "أبعد", "ashhar": "أشهر", "rasmiya": "رسمية",
    "ma3roof": "معروف", "ma3roofa": "معروفة",
}
