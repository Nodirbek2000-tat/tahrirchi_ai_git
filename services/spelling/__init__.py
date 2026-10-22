"""O'zbek imlosini tuzatish: qoidalar (AI'siz) + murakkab gaplarda tejamkor AI."""

from .converter import KIND_LABELS, SpellConverter, SpellCtx
from .lexicon import get_lexicon

__all__ = ["KIND_LABELS", "SpellConverter", "SpellCtx", "get_lexicon"]
