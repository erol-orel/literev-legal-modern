"""Download the optional spaCy models used by multilingual preprocessing.

German and Italian decisions (e.g. Swiss Federal Court) are preprocessed with
their own spaCy models. Only French ships by default; this command installs the
German/Italian models so lemmatization runs for those languages instead of the
graceful token fallback.

Examples
--------
Install the German and Italian models (the default)::

    python manage.py ensure_language_models

Install a specific set::

    python manage.py ensure_language_models --languages de
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandParser

# Language code -> spaCy model, mirroring lr_preprocessing.utils.
SPACY_MODELS = {
    "fr": "fr_core_news_sm",
    "de": "de_core_news_sm",
    "it": "it_core_news_sm",
}
DEFAULT_LANGUAGES = ["de", "it"]


class Command(BaseCommand):
    help = "Download optional spaCy models (de/it) for DE/IT preprocessing."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--languages",
            nargs="+",
            default=list(DEFAULT_LANGUAGES),
            choices=sorted(SPACY_MODELS),
            help="Language codes whose spaCy model to install (default: de it).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        import spacy
        import spacy.cli

        installed = 0
        for lang in options["languages"]:
            model = SPACY_MODELS[lang]
            if spacy.util.is_package(model):
                self.stdout.write(f"{model} already installed — skipping.")
                continue
            self.stdout.write(f"Downloading {model}…")
            spacy.cli.download(model)
            installed += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Language models ready ({installed} newly installed)."
            )
        )
