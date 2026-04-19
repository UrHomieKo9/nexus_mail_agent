"""Digital Twin — Linguistic profile extraction from Sent folder."""

import re
from collections import Counter
from datetime import datetime, timezone

from backend.api.schemas import EmailMessage, LinguisticProfile
from backend.core.config import settings
from backend.core.logger import get_logger
from backend.memory.vector_store import VectorStore

logger = get_logger("profiler")

# Common greetings and sign-offs to detect
GREETINGS = [
    "hi", "hey", "hello", "dear", "good morning", "good afternoon",
    "good evening", "greetings", "howdy", "yo",
]

SIGNOFFS = [
    "best", "regards", "cheers", "thanks", "sincerely", "warmly",
    "best regards", "kind regards", "best wishes", "take care",
    "looking forward", "talk soon", "catch you later", "see you",
]


class Profiler:
    """Analyses a user's Sent folder to calculate their Linguistic Profile.

    The Copywriter agent uses this profile so replies sound like
    the user — not a bot.
    """

    def __init__(self):
        self.vector_store = VectorStore()

    def analyze_emails(self, emails: list[EmailMessage]) -> LinguisticProfile:
        """Analyze a list of sent emails and produce a linguistic profile.

        Args:
            emails: List of sent emails to analyze.

        Returns:
            LinguisticProfile with all computed metrics.
        """
        if not emails:
            return LinguisticProfile()

        # Compute metrics
        sentence_lengths = []
        greetings_found = Counter()
        signoffs_found = Counter()
        formality_scores = []
        word_freq = Counter()
        total_words = 0

        for email in emails:
            body = email.body_clean.lower()
            if not body:
                continue

            # Sentence analysis
            sentences = [s.strip() for s in re.split(r'[.!?]+', body) if s.strip()]
            for sentence in sentences:
                words = sentence.split()
                sentence_lengths.append(len(words))
                total_words += len(words)
                word_freq.update(words)

            # Greeting detection (first 2 sentences)
            first_text = " ".join(sentences[:2]) if sentences else ""
            for greeting in GREETINGS:
                if greeting in first_text:
                    greetings_found[greeting] += 1

            # Sign-off detection (last 2 sentences)
            last_text = " ".join(sentences[-2:]) if len(sentences) >= 2 else ""
            for signoff in SIGNOFFS:
                if signoff in last_text:
                    signoffs_found[signoff] += 1

            # Formality scoring
            formality = self._score_formality(body)
            formality_scores.append(formality)

        avg_sentence_length = (
            sum(sentence_lengths) / len(sentence_lengths)
            if sentence_lengths
            else 0.0
        )

        avg_formality = (
            sum(formality_scores) / len(formality_scores)
            if formality_scores
            else 5.0
        )

        # Top greetings and sign-offs
        top_greetings = [g for g, _ in greetings_found.most_common(5)]
        top_signoffs = [s for s, _ in signoffs_found.most_common(5)]

        # Top vocabulary (filter out common stop words)
        top_vocab = {
            word: count
            for word, count in word_freq.most_common(100)
            if len(word) > 3 and word not in self._stop_words()
        }

        return LinguisticProfile(
            avg_sentence_length=round(avg_sentence_length, 1),
            common_greetings=top_greetings,
            common_signoffs=top_signoffs,
            formality_level=round(avg_formality, 1),
            vocabulary_frequency=dict(top_vocab),
            email_count_analyzed=len(emails),
            last_updated=datetime.now(timezone.utc),
        )

    async def build_profile(self, user_id: str, sent_emails: list[EmailMessage]) -> LinguisticProfile:
        """Build and persist a user's linguistic profile.

        Args:
            user_id: The user's unique identifier.
            sent_emails: List of the user's sent emails.

        Returns:
            The computed LinguisticProfile.
        """
        profile = self.analyze_emails(sent_emails)
        profile.user_id = user_id

        # Persist to Supabase
        from supabase import create_client

        supabase = create_client(settings.supabase_url, settings.supabase_service_key)

        record = {
            "user_id": user_id,
            "avg_sentence_length": profile.avg_sentence_length,
            "common_greetings": profile.common_greetings,
            "common_signoffs": profile.common_signoffs,
            "formality_level": profile.formality_level,
            "vocabulary_frequency": profile.vocabulary_frequency,
            "email_count_analyzed": profile.email_count_analyzed,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        existing = (
            supabase.table("linguistic_profiles")
            .select("id")
            .eq("user_id", user_id)
            .execute()
        )

        if existing.data:
            supabase.table("linguistic_profiles").update(record).eq(
                "user_id", user_id
            ).execute()
            logger.info("profile_updated", user_id=user_id)
        else:
            supabase.table("linguistic_profiles").insert(record).execute()
            logger.info("profile_created", user_id=user_id)

        return profile

    async def get_profile(self, user_id: str) -> LinguisticProfile | None:
        """Retrieve a stored linguistic profile."""
        from supabase import create_client

        supabase = create_client(settings.supabase_url, settings.supabase_service_key)

        result = (
            supabase.table("linguistic_profiles")
            .select("*")
            .eq("user_id", user_id)
            .execute()
        )

        if not result.data:
            return None

        row = result.data[0]
        return LinguisticProfile(
            user_id=row["user_id"],
            avg_sentence_length=row.get("avg_sentence_length", 0.0),
            common_greetings=row.get("common_greetings", []),
            common_signoffs=row.get("common_signoffs", []),
            formality_level=row.get("formality_level", 5.0),
            vocabulary_frequency=row.get("vocabulary_frequency", {}),
            email_count_analyzed=row.get("email_count_analyzed", 0),
            last_updated=row.get("updated_at"),
        )

    @staticmethod
    def _score_formality(text: str) -> float:
        """Score formality level of text on 0-10 scale.

        Indicators:
        - Contractions → informal
        - Long words → formal
        - Exclamation marks → informal
        - Slang/abbreviations → informal
        """
        score = 5.0  # Start neutral

        # Contractions reduce formality
        contractions = re.findall(r"\b\w+'\w+\b", text)
        score -= len(contractions) * 0.3

        # Exclamation marks reduce formality
        exclamations = text.count("!")
        score -= exclamations * 0.5

        # Words with 7+ characters increase formality
        long_words = len(re.findall(r"\b\w{7,}\b", text))
        total_words = len(text.split())
        if total_words > 0:
            long_ratio = long_words / total_words
            score += long_ratio * 5.0

        # Clamp to 0-10
        return max(0.0, min(10.0, score))

    @staticmethod
    def _stop_words() -> set[str]:
        """Common English stop words to exclude from vocabulary frequency."""
        return {
            "that", "this", "with", "have", "from", "they", "been",
            "said", "each", "which", "their", "will", "other", "about",
            "many", "then", "them", "these", "some", "would", "make",
            "like", "into", "time", "very", "when", "come", "could",
            "more", "over", "such", "after", "also", "just", "than",
        }