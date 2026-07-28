"""Low-level, dependency-free predicates and constants for query analysis.

Every regex and keyword set used anywhere in `tara.classification` is
defined and compiled exactly once here, at import time. `features.py`
and `rules.py` only call these functions and read these constants; they
never define their own patterns. This is what keeps `classify()` cheap
even under repeated calls: no pattern is ever recompiled per query, and
every lookup here is either a single `re.match` against a short string
or an O(1) set/dict membership check.
"""
from __future__ import annotations

import re
from collections.abc import Iterable

from tara.core.types import Language

# --- Tokenization ------------------------------------------------------------

# Preserves internal "." / "/" / "\\" so multi-segment tokens like
# "tara/parsing/repository_parser.py" or "utils.py" survive as a single
# token instead of being shredded into fragments -- both keyword
# extraction and file-path/symbol detection depend on that.
_WORD_PATTERN = re.compile(r"[A-Za-z0-9_]+(?:[./\\][A-Za-z0-9_]+)*")


def tokenize(text: str) -> list[str]:
    """Split `text` into word-like tokens, preserving path/extension separators."""
    return _WORD_PATTERN.findall(text)


# --- Stop words ----------------------------------------------------------------

STOP_WORDS: frozenset[str] = frozenset(
    {
        "a", "an", "and", "are", "as", "at", "be", "by", "can", "could",
        "did", "do", "does", "for", "from", "had", "has", "have", "how",
        "i", "in", "into", "is", "it", "its", "of", "on", "or", "should",
        "so", "that", "the", "their", "there", "this", "to", "was",
        "were", "what", "when", "where", "which", "who", "why", "will",
        "with", "would", "you", "your",
    }
)


def is_stop_word(token: str) -> bool:
    """Return whether `token` is a common English filler word, not a search term."""
    return token.lower() in STOP_WORDS


# --- Naming-convention predicates -----------------------------------------------
#
# Each pattern requires at least two "humps"/segments made of a real
# letter run (not a single bare capital), so short all-caps acronyms
# ("JWT", "API") and ordinary capitalized English words ("Find", "The")
# are deliberately excluded here -- see `is_acronym` for the former.

_PASCAL_CASE_PATTERN = re.compile(r"^(?:[A-Z][a-z0-9]+){2,}$")
_CAMEL_CASE_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:[A-Z][a-z0-9]+)+$")
_SNAKE_CASE_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)+$")
_CONSTANT_CASE_PATTERN = re.compile(r"^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+$")
_ACRONYM_PATTERN = re.compile(r"^[A-Z]{2,}$")


def is_pascal_case(token: str) -> bool:
    """E.g. `RepositoryParser`, `TreeSitterRepositoryParser`."""
    return bool(_PASCAL_CASE_PATTERN.match(token))


def is_camel_case(token: str) -> bool:
    """E.g. `parseRepository`, `getUserById`."""
    return bool(_CAMEL_CASE_PATTERN.match(token))


def is_snake_case(token: str) -> bool:
    """E.g. `parse_repository`, `max_file_size_bytes`."""
    return bool(_SNAKE_CASE_PATTERN.match(token))


def is_constant_case(token: str) -> bool:
    """E.g. `MAX_FILE_SIZE_BYTES`."""
    return bool(_CONSTANT_CASE_PATTERN.match(token))


def is_acronym(token: str) -> bool:
    """E.g. `JWT`, `API`, `SQL`, `CVE` -- two or more bare uppercase letters."""
    return bool(_ACRONYM_PATTERN.match(token))


def looks_like_identifier(token: str) -> bool:
    """Return True if `token` reads like a code symbol rather than an ordinary English word."""
    return (
        is_pascal_case(token)
        or is_camel_case(token)
        or is_snake_case(token)
        or is_constant_case(token)
        or is_acronym(token)
    )


# --- Quoted identifiers ----------------------------------------------------------

_QUOTED_PATTERN = re.compile(r"[\"'`]([^\"'`]+)[\"'`]")


def extract_quoted(text: str) -> list[str]:
    """Return the contents of every `"..."` / `'...'` / `` `...` `` span in `text`, in order."""
    return _QUOTED_PATTERN.findall(text)


# --- File paths / extensions -----------------------------------------------------

KNOWN_EXTENSIONS: frozenset[str] = frozenset(
    {
        "py", "pyi", "js", "jsx", "mjs", "cjs", "ts", "tsx", "java", "go",
        "rs", "c", "h", "cpp", "cc", "cxx", "hpp", "hxx", "md", "json",
        "yaml", "yml", "toml", "txt", "cfg", "ini",
    }
)

_FILE_PATH_PATTERN = re.compile(
    r"^[\w.\-]+(?:[/\\][\w.\-]+)*\.(?:" + "|".join(sorted(KNOWN_EXTENSIONS)) + r")$"
)


def looks_like_file_path(token: str) -> bool:
    """Return whether `token` is a bare filename or path ending in a known source/config extension."""
    return bool(_FILE_PATH_PATTERN.match(token))


def extract_extension(token: str) -> str | None:
    """Return `token`'s file extension if it's one TARA recognizes, else None."""
    if "." not in token:
        return None
    suffix = token.rsplit(".", 1)[-1].lower()
    return suffix if suffix in KNOWN_EXTENSIONS else None


# --- Language mentions -------------------------------------------------------------

_LANGUAGE_KEYWORDS: dict[str, Language] = {
    "python": Language.PYTHON,
    "py": Language.PYTHON,
    "javascript": Language.JAVASCRIPT,
    "js": Language.JAVASCRIPT,
    "typescript": Language.TYPESCRIPT,
    "ts": Language.TYPESCRIPT,
    "java": Language.JAVA,
    "go": Language.GO,
    "golang": Language.GO,
    "rust": Language.RUST,
    "c++": Language.CPP,
    "cpp": Language.CPP,
    "c": Language.C,
}


def detect_language(tokens: Iterable[str]) -> Language | None:
    """Return the first `Language` mentioned in `tokens`, or None.

    Only the first match is returned by design: a query mentioning two
    languages ("convert this Python script to Go") is a genuine
    ambiguity a single `language_hint` field can't resolve, so this
    picks a deterministic, documented winner (first mention) rather than
    guessing at intent.
    """
    for token in tokens:
        language = _LANGUAGE_KEYWORDS.get(token.lower())
        if language is not None:
            return language
    return None


# --- Intent keyword sets --------------------------------------------------------
#
# Matched as exact tokens (via set membership on a lowercased token set),
# never as substrings -- so e.g. the GENERATE trigger "implement" never
# accidentally fires on "implemented" or "implementation". Plural/-ing/
# -ed inflections are listed explicitly where they matter, trading a
# slightly longer set for avoiding regex entirely on this hot path.

SEARCH_KEYWORDS: frozenset[str] = frozenset({"find", "finds", "search", "searching", "locate", "lookup", "grep", "where"})
IMPLEMENTATION_KEYWORDS: frozenset[str] = frozenset(
    {"implemented", "implementation", "implementations", "implements", "defined", "definition", "definitions"}
)
EXPLAIN_KEYWORDS: frozenset[str] = frozenset({"explain", "explains", "explained", "understand", "describe", "describes", "clarify"})
DEBUG_KEYWORDS: frozenset[str] = frozenset(
    {"debug", "debugging", "investigate", "investigating", "diagnose", "diagnosing", "troubleshoot", "troubleshooting"}
)
BUG_FIX_KEYWORDS: frozenset[str] = frozenset(
    {"fix", "fixes", "fixing", "bug", "bugs", "broken", "crash", "crashes", "crashing", "fails", "failing", "failed", "error", "errors"}
)
REFACTOR_KEYWORDS: frozenset[str] = frozenset(
    {"refactor", "refactoring", "restructure", "restructuring", "cleanup", "clean", "simplify", "simplifying", "rename", "renaming", "reorganize", "reorganizing"}
)
GENERATE_KEYWORDS: frozenset[str] = frozenset(
    {"generate", "generating", "create", "creating", "implement", "implementing", "scaffold", "scaffolding", "add", "adding", "build", "building"}
)
TEST_KEYWORDS: frozenset[str] = frozenset({"test", "tests", "testing", "coverage", "unittest", "pytest"})
DOCUMENTATION_KEYWORDS: frozenset[str] = frozenset(
    {"document", "documents", "documenting", "documentation", "docstring", "docstrings", "readme", "comment", "comments", "commenting"}
)
ARCHITECTURE_KEYWORDS: frozenset[str] = frozenset({"architecture", "design", "structure", "overview", "diagram", "flow", "flows"})
DEPENDENCY_KEYWORDS: frozenset[str] = frozenset(
    {"dependency", "dependencies", "imports", "depends", "depend", "requires", "require", "package", "packages"}
)
SECURITY_KEYWORDS: frozenset[str] = frozenset(
    {"security", "vulnerability", "vulnerabilities", "vulnerable", "exploit", "exploits", "cve", "injection", "auth", "authentication", "authorization"}
)
PERFORMANCE_KEYWORDS: frozenset[str] = frozenset(
    {"performance", "slow", "slowness", "latency", "optimize", "optimizing", "optimization", "bottleneck", "bottlenecks", "memory", "leak", "leaks"}
)
# Deliberately excludes "dependency"/"dependencies"/"imports" -- those
# already set graph_required=True via DEPENDENCY_KEYWORDS above.
GRAPH_TRIGGER_KEYWORDS: frozenset[str] = frozenset(
    {"trace", "tracing", "calls", "caller", "callers", "callee", "callees", "inherits", "inheritance", "path", "paths"}
)
REASONING_TRIGGER_KEYWORDS: frozenset[str] = frozenset({"why"})

# Word pairs that signal an "explain"-shaped question even without one
# of EXPLAIN_KEYWORDS present, e.g. "What does X do?" / "How does X work?".
_EXPLAIN_QUESTION_PAIRS: tuple[frozenset[str], ...] = (
    frozenset({"what", "do"}),
    frozenset({"what", "does"}),
    frozenset({"what", "is"}),
    frozenset({"how", "does"}),
    frozenset({"how", "do"}),
    frozenset({"how", "works"}),
)


def looks_like_explain_question(token_set: frozenset[str]) -> bool:
    """Return whether `token_set` contains one of the known "explain"-shaped word pairs."""
    return any(pair <= token_set for pair in _EXPLAIN_QUESTION_PAIRS)
