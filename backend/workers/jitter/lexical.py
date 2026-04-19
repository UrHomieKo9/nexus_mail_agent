"""Lexical Jitter — synonym substitution for anti-spam variation."""

import random

from backend.core.logger import get_logger

logger = get_logger("lexical_jitter")

# Synonym map for common business phrases.
# Each key maps to a list of equivalent alternatives.
_SYNONYM_MAP: dict[str, list[str]] = {
    "please find attached": [
        "attached you'll find",
        "I've attached",
        "see attached",
        "please see the attachment",
    ],
    "i hope this email finds you well": [
        "hope you're doing well",
        "hope all is well",
        "trust you're well",
        "I hope you're having a great day",
    ],
    "looking forward to hearing from you": [
        "looking forward to your response",
        "excited to hear your thoughts",
        "eager to hear back",
        "I'd love to hear your thoughts",
    ],
    "don't hesitate to reach out": [
        "feel free to reach out",
        "happy to chat anytime",
        "drop me a line if you have questions",
        "let me know if you have any questions",
    ],
    "thank you for your time": [
        "thanks for your time",
        "appreciate your time",
        "grateful for your time",
        "thanks for taking the time",
    ],
    "best regards": [
        "kind regards",
        "best",
        "warm regards",
        "regards",
        "all the best",
    ],
    "i wanted to follow up": [
        "just following up",
        "circling back on",
        "touching base on",
        "checking in on",
    ],
    "at your earliest convenience": [
        "when you get a chance",
        "whenever works for you",
        "at your convenience",
        "when you have a moment",
    ],
    "i would like to schedule a meeting": [
        "can we set up a call",
        "could we hop on a quick call",
        "would love to find time to chat",
        "let's find a time to connect",
    ],
    "as discussed": [
        "as we talked about",
        "following our conversation",
        "per our discussion",
        "as mentioned",
    ],
}

# Word-level synonyms for variety
_WORD_SYNONYMS: dict[str, list[str]] = {
    "great": ["excellent", "fantastic", "wonderful", "terrific"],
    "help": ["assist", "support", "aid"],
    "important": ["key", "crucial", "essential", "critical"],
    "quickly": ["promptly", "soon", "swiftly", "right away"],
    "discuss": ["talk about", "go over", "explore", "review"],
    "opportunity": ["chance", "possibility", "prospect"],
    "interested": ["keen", "eager", "curious", "enthusiastic"],
    "provide": ["share", "offer", "supply", "deliver"],
    "improve": ["enhance", "boost", "strengthen", "optimize"],
    "information": ["details", "info", "data", "insights"],
}


class LexicalJitter:
    """Apply synonym substitution to vary email text for anti-spam."""

    def __init__(self, intensity: float = 0.5):
        """Initialize lexical jitter.

        Args:
            intensity: How aggressively to substitute (0.0–1.0).
                       0.0 = no changes, 1.0 = replace everything possible.
        """
        self.intensity = max(0.0, min(1.0, intensity))

    def apply(self, text: str) -> str:
        """Apply lexical jitter to the given text.

        - Phrase-level substitution (higher fidelity)
        - Word-level substitution (fine-grained variety)

        Args:
            text: The email body to jitter.

        Returns:
            The modified text with synonym substitutions applied.
        """
        if not text:
            return text

        result = text
        substitutions = 0

        # Phase 1: Phrase-level substitution
        for phrase, alternatives in _SYNONYM_MAP.items():
            if phrase in result.lower():
                if random.random() < self.intensity:
                    replacement = random.choice(alternatives)
                    # Preserve original case style
                    result = self._case_aware_replace(result, phrase, replacement)
                    substitutions += 1

        # Phase 2: Word-level substitution (only if intensity is high enough)
        if self.intensity > 0.3:
            result = self._apply_word_synonyms(result)

        logger.debug(
            "lexical_jitter_applied",
            substitutions=substitutions,
            intensity=self.intensity,
        )
        return result

    def _apply_word_synonyms(self, text: str) -> str:
        """Apply word-level synonym substitution."""
        words = text.split()
        result_words = []

        for word in words:
            clean = word.lower().strip(".,!?;:\"'()")
            if clean in _WORD_SYNONYMS and random.random() < self.intensity * 0.3:
                replacement = random.choice(_WORD_SYNONYMS[clean])
                # Preserve punctuation around the word
                prefix = ""
                suffix = ""
                for ch in word:
                    if ch.isalpha():
                        break
                    prefix += ch
                for ch in reversed(word):
                    if ch.isalpha():
                        break
                    suffix = ch + suffix
                # Preserve capitalization
                if word[len(prefix) : len(prefix) + 1].isupper():
                    replacement = replacement.capitalize()
                result_words.append(f"{prefix}{replacement}{suffix}")
            else:
                result_words.append(word)

        return " ".join(result_words)

    @staticmethod
    def _case_aware_replace(text: str, old: str, new: str) -> str:
        """Replace phrase preserving the original case style."""
        import re

        pattern = re.compile(re.escape(old), re.IGNORECASE)
        match = pattern.search(text)
        if not match:
            return text

        original = match.group()
        if original[0].isupper():
            new = new[0].upper() + new[1:]
        if original.isupper():
            new = new.upper()

        return pattern.sub(new, text, count=1)
