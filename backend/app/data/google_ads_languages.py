"""Google Ads language constants — the full targetable set, bundled as data.

Google Ads language targeting uses a small, stable set of ~50 language
constants (criteria of the form ``languageConstants/<id>``). Rather than make
the wizards force operators to type raw numeric ids ("the language shouldn't be
numbers"), we bundle the named set here and serve it from
``/api/targeting/languages`` so every campaign wizard shows a proper named
multi-select with English (1000) as the default.

Source of truth: pulled live from the Google Ads API
(``SELECT language_constant.id, language_constant.name, language_constant.code
FROM language_constant WHERE language_constant.targetable = true``) — 51 rows,
2026-08. Kept as static data because the set changes rarely and the wizards
must render instantly without a per-open API round-trip. English is pinned
FIRST because it is the fleet's default targeting language.

Note: Google Ads has NO "English (Australia)" language constant — English is a
single constant (1000). Country-specific labelling ("English (Australia)") is a
Google Ads *web-UI* artifact of the account's home locale, never a criterion
this app can or does set.
"""

from __future__ import annotations

from typing import Dict, List

# id · name · code (BCP-47-ish / Google's own code). English pinned first; the
# remainder are alphabetical by name.
LANGUAGES: List[Dict[str, str]] = [
    {"id": "1000", "name": "English", "code": "en"},
    {"id": "1019", "name": "Arabic", "code": "ar"},
    {"id": "1056", "name": "Bengali", "code": "bn"},
    {"id": "1020", "name": "Bulgarian", "code": "bg"},
    {"id": "1038", "name": "Catalan", "code": "ca"},
    {"id": "1017", "name": "Chinese (simplified)", "code": "zh_CN"},
    {"id": "1018", "name": "Chinese (traditional)", "code": "zh_TW"},
    {"id": "1039", "name": "Croatian", "code": "hr"},
    {"id": "1021", "name": "Czech", "code": "cs"},
    {"id": "1009", "name": "Danish", "code": "da"},
    {"id": "1010", "name": "Dutch", "code": "nl"},
    {"id": "1043", "name": "Estonian", "code": "et"},
    {"id": "1042", "name": "Filipino", "code": "tl"},
    {"id": "1011", "name": "Finnish", "code": "fi"},
    {"id": "1002", "name": "French", "code": "fr"},
    {"id": "1001", "name": "German", "code": "de"},
    {"id": "1022", "name": "Greek", "code": "el"},
    {"id": "1072", "name": "Gujarati", "code": "gu"},
    {"id": "1027", "name": "Hebrew", "code": "iw"},
    {"id": "1023", "name": "Hindi", "code": "hi"},
    {"id": "1024", "name": "Hungarian", "code": "hu"},
    {"id": "1026", "name": "Icelandic", "code": "is"},
    {"id": "1025", "name": "Indonesian", "code": "id"},
    {"id": "1004", "name": "Italian", "code": "it"},
    {"id": "1005", "name": "Japanese", "code": "ja"},
    {"id": "1086", "name": "Kannada", "code": "kn"},
    {"id": "1012", "name": "Korean", "code": "ko"},
    {"id": "1028", "name": "Latvian", "code": "lv"},
    {"id": "1029", "name": "Lithuanian", "code": "lt"},
    {"id": "1102", "name": "Malay", "code": "ms"},
    {"id": "1098", "name": "Malayalam", "code": "ml"},
    {"id": "1101", "name": "Marathi", "code": "mr"},
    {"id": "1013", "name": "Norwegian", "code": "no"},
    {"id": "1064", "name": "Persian", "code": "fa"},
    {"id": "1030", "name": "Polish", "code": "pl"},
    {"id": "1014", "name": "Portuguese", "code": "pt"},
    {"id": "1110", "name": "Punjabi", "code": "pa"},
    {"id": "1032", "name": "Romanian", "code": "ro"},
    {"id": "1031", "name": "Russian", "code": "ru"},
    {"id": "1035", "name": "Serbian", "code": "sr"},
    {"id": "1033", "name": "Slovak", "code": "sk"},
    {"id": "1034", "name": "Slovenian", "code": "sl"},
    {"id": "1003", "name": "Spanish", "code": "es"},
    {"id": "1015", "name": "Swedish", "code": "sv"},
    {"id": "1130", "name": "Tamil", "code": "ta"},
    {"id": "1131", "name": "Telugu", "code": "te"},
    {"id": "1044", "name": "Thai", "code": "th"},
    {"id": "1037", "name": "Turkish", "code": "tr"},
    {"id": "1036", "name": "Ukrainian", "code": "uk"},
    {"id": "1041", "name": "Urdu", "code": "ur"},
    {"id": "1040", "name": "Vietnamese", "code": "vi"},
]

# The default targeting language the wizards preselect.
DEFAULT_LANGUAGE_ID = "1000"  # English

_BY_ID: Dict[str, Dict[str, str]] = {lang["id"]: lang for lang in LANGUAGES}


def get_languages() -> List[Dict[str, str]]:
    """Return the full language list (English first, then alphabetical)."""
    return list(LANGUAGES)


def language_name(language_id: str) -> str:
    """Resolve a language id to its display name, or the raw id if unknown."""
    lang = _BY_ID.get(str(language_id))
    return lang["name"] if lang else str(language_id)
