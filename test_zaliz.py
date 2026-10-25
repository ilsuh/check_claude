import os
import unittest

import zaliz

DICT = zaliz.Dictionary([os.path.join(zaliz.DATA_DIR, n) for n in zaliz.DATA_FILES])


def forms(lemma):
    """Все словоформы леммы без ударений."""
    return {zaliz.strip_accents(f.text)
            for meaning in DICT.parse(lemma) for v in meaning
            for _, fs in zaliz.inflect(v) for f in fs}


class ZalizTest(unittest.TestCase):
    def test_noun(self):
        self.assertTrue({"стол", "стола", "столами", "столах"} <= forms("стол"))

    def test_verb_with_other_bases(self):
        self.assertTrue({"идти", "шёл", "шла", "иду", "идёшь", "шедши"} <= forms("идти"))

    def test_absent_forms_skipped(self):
        # у глагола совершенного вида нет форм настоящего времени
        self.assertNotIn("", forms("пасть"))
        self.assertFalse(any(f.endswith("-") for f in forms("абазинский")))

    def test_pronoun(self):
        self.assertTrue({"я", "меня", "мне", "мной", "мною"} <= forms("я"))

    def test_form_lookup(self):
        self.assertIn("стол", DICT.lemmas_of_form("столами"))
        self.assertIn("идти", DICT.lemmas_of_form("шел"))

    def test_second_prepositional(self):
        self.assertIn("в лесу́", zaliz.answer(DICT, "лес"))

    def test_every_entry_renders(self):
        for lemma in DICT.entries:
            zaliz.render_lemma(DICT, lemma)


if __name__ == "__main__":
    unittest.main()
