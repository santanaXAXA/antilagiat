import re
import math

AI_PHRASES_RU = [
    "таким образом", "следует отметить", "в заключение", "необходимо подчеркнуть",
    "важно отметить", "следует также", "в данном контексте", "с одной стороны",
    "с другой стороны", "немаловажную роль", "в современном мире",
    "в рамках данной", "на основании вышеизложенного", "подводя итог",
    "стоит отметить", "необходимо учитывать", "ключевым аспектом", "особую роль",
    "следует подчеркнуть", "в целом можно сказать", "резюмируя вышесказанное",
    "принимая во внимание", "в свете вышесказанного", "комплексный подход",
    "всестороннее рассмотрение", "неотъемлемой частью",
    "существенное значение", "играет важную роль", "следует рассмотреть",
    "нельзя не отметить", "представляется возможным", "в ходе исследования",
    "данная работа", "данная статья", "как было сказано выше",
]

AI_PHRASES_EN = [
    "in conclusion", "it is worth noting", "it is important to note",
    "furthermore", "moreover", "in addition", "it should be noted",
    "on the other hand", "plays a crucial role", "to summarize",
    "in summary", "delve into", "in today's world", "at its core",
    "multifaceted", "in the realm of", "shed light on", "tapestry",
    "pivotal", "paramount",
]

REWRITES = {
    "таким образом":               ["итак", "значит", "в общем"],
    "следует отметить":            ["стоит сказать", "нужно упомянуть", "замечу"],
    "в заключение":                ["в конце", "напоследок", "под конец"],
    "необходимо подчеркнуть":      ["подчеркну", "хочу выделить", "важно"],
    "важно отметить":              ["замечу", "стоит сказать", "нужно сказать"],
    "следует также":               ["также", "ещё", "добавлю"],
    "в данном контексте":          ["здесь", "в этом случае", "при этом"],
    "с одной стороны":             ["во-первых", "с одного угла", "если смотреть так"],
    "с другой стороны":            ["но", "однако", "зато"],
    "немаловажную роль":           ["важную роль", "большое значение"],
    "в современном мире":          ["сейчас", "сегодня", "в наши дни"],
    "в рамках данной":             ["в этой", "в нашей", "здесь"],
    "на основании вышеизложенного":["из этого", "из сказанного", "из всего выше"],
    "подводя итог":                ["в итоге", "в конце концов", "резюмируя"],
    "стоит отметить":              ["замечу", "скажу", "упомяну"],
    "необходимо учитывать":        ["нужно помнить", "важно учесть", "стоит иметь в виду"],
    "ключевым аспектом":           ["главным", "основным", "важным моментом"],
    "следует подчеркнуть":         ["подчеркну", "выделю", "акцентирую"],
    "в целом можно сказать":       ["в целом", "в общем", "если коротко"],
    "резюмируя вышесказанное":     ["итак", "в итоге", "если подвести итог"],
    "принимая во внимание":        ["учитывая", "если взять в расчёт", "с учётом"],
    "комплексный подход":          ["разносторонний подход", "несколько методов"],
    "существенное значение":       ["важное значение", "большую роль"],
    "играет важную роль":          ["важен", "имеет значение", "влияет"],
    "нельзя не отметить":          ["отмечу", "скажу", "стоит сказать"],
    "представляется возможным":    ["можно", "есть возможность", "реально"],
    "в ходе исследования":         ["в процессе", "исследуя", "изучая"],
    "данная работа":               ["эта работа", "наше исследование"],
    "данная статья":               ["эта статья", "эта работа"],
    "как было сказано выше":       ["как упоминалось", "как я писал выше", "ранее"],
    "furthermore":                 ["also", "plus", "and"],
    "moreover":                    ["also", "besides", "on top of that"],
    "in addition":                 ["also", "and", "plus"],
    "in conclusion":               ["finally", "to wrap up", "in the end"],
    "it is worth noting":          ["note that", "importantly"],
    "it is important to note":     ["note that", "keep in mind"],
    "plays a crucial role":        ["is key", "matters a lot", "is important"],
    "in today's world":            ["today", "nowadays", "these days"],
    "delve into":                  ["look at", "explore", "examine"],
}

BORROW_PHRASES = [
    "согласно определению", "по мнению", "как отмечает", "как указывает",
    "исследования показывают", "по данным", "согласно исследованиям",
    "ряд авторов", "многие учёные", "в научной литературе",
    "принято считать", "общепризнанным является", "классическое определение",
    "термин был введён", "впервые описан", "широко известно",
    "является общепринятым", "в соответствии с теорией",
    "данная концепция", "согласно классификации",
]


def split_sentences(text: str) -> list[str]:
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    return [p for p in parts if len(p.split()) >= 3]


def detect_citations(text: str) -> dict:
    """Detect quoted and cited fragments."""
    # Quoted text: «...» or "..."
    quotes_ru = re.findall(r'«[^»]{5,}»', text)
    quotes_en = re.findall(r'"[^"]{5,}"', text)
    all_quotes = quotes_ru + quotes_en

    # Academic reference markers: [1], (Иванов, 2020), footnote numbers
    ref_markers = re.findall(r'\[\d+\]|\(\s*[А-ЯA-Z][а-яa-z]+,?\s*\d{4}\s*\)', text)

    # Bibliography lines: "1. Автор А.А. Название..."
    bib_lines = re.findall(r'^\s*\d+\.\s+[А-ЯA-Z][а-яёa-z]+', text, re.MULTILINE)

    quoted_chars = sum(len(q) for q in all_quotes)
    total_chars = len(text)
    quote_ratio = quoted_chars / total_chars if total_chars > 0 else 0

    refs_count = len(ref_markers) + len(bib_lines)

    # Score: how much of text is citations
    score = min(100, round(quote_ratio * 120 + refs_count * 4))

    found = [q[:60] + ("…" if len(q) > 60 else "") for q in all_quotes[:4]]

    return {
        "score": score,
        "quotes_count": len(all_quotes),
        "refs_count": refs_count,
        "found": found,
    }


def detect_borrowing(text: str) -> dict:
    """Heuristic: detect patterns typical of copied/borrowed academic text."""
    lower = text.lower()
    words = text.split()
    if not words:
        return {"score": 0, "found": []}

    # Borrowing phrase hits
    hits = [p for p in BORROW_PHRASES if p in lower]
    phrase_ratio = len(hits) / (len(words) / 100)

    # Very long sentences without punctuation variety = possibly copied blocks
    sentences = split_sentences(text)
    long_sents = [s for s in sentences if len(s.split()) > 30]
    long_ratio = len(long_sents) / len(sentences) if sentences else 0

    score = min(100, round(phrase_ratio * 14 + long_ratio * 30))

    return {
        "score": score,
        "found": hits[:4],
    }


def detect_ai(text: str) -> dict:
    """Detect AI-generated content."""
    sentences = split_sentences(text)
    words = re.findall(r'\b\w+\b', text.lower())
    total_words = len(words)

    # Burstiness
    if len(sentences) >= 3:
        lengths = [len(s.split()) for s in sentences]
        mean = sum(lengths) / len(lengths)
        std = math.sqrt(sum((l - mean) ** 2 for l in lengths) / len(lengths))
        cv = std / mean if mean > 0 else 0
        if cv >= 0.5:   burst = 5
        elif cv >= 0.4: burst = 20
        elif cv >= 0.3: burst = 45
        elif cv >= 0.2: burst = 65
        else:           burst = 85
    else:
        burst = 50

    # AI phrases
    lower = text.lower()
    ai_hits = [p for p in AI_PHRASES_RU + AI_PHRASES_EN if p in lower]
    phrase_s = min(100, len(ai_hits) / (total_words / 100) * 18) if total_words else 0

    # Lexical diversity
    unique = len(set(words))
    ttr = unique / total_words if total_words else 1
    if ttr >= 0.6:   div = 10
    elif ttr >= 0.5: div = 30
    elif ttr >= 0.4: div = 55
    else:            div = 75

    # Avg sentence length
    if sentences:
        avg = sum(len(s.split()) for s in sentences) / len(sentences)
        sent_s = 65 if 14 <= avg <= 22 else (15 if avg < 8 or avg > 35 else 35)
    else:
        sent_s = 50

    # Punctuation
    informal = len(re.findall(r'[!…\-—]', text))
    pw = len(text.split())
    ratio = informal / pw if pw else 0
    punct = 10 if ratio > 0.05 else (35 if ratio > 0.02 else 70)

    score = round(burst * 0.30 + phrase_s * 0.25 + div * 0.20 + sent_s * 0.15 + punct * 0.10)

    return {
        "score": score,
        "found_phrases": ai_hits[:5],
    }


def score_sentence(sent: str) -> int:
    """Score a single sentence for AI likelihood (0–100)."""
    lower = sent.lower()
    words = sent.split()
    score = 0

    # AI phrase match
    phrase_hits = sum(1 for p in AI_PHRASES_RU + AI_PHRASES_EN if p in lower)
    score += min(50, phrase_hits * 25)

    # Sentence length in AI sweet spot
    wc = len(words)
    if 14 <= wc <= 22:
        score += 20
    elif 10 <= wc <= 26:
        score += 10

    # No informal punctuation
    if not re.search(r'[!…—]', sent):
        score += 15

    # Starts with typical AI transition word
    first = lower.split()[0] if words else ""
    if first in ("таким", "следует", "важно", "необходимо", "кроме", "также",
                 "однако", "moreover", "furthermore", "additionally", "in"):
        score += 15

    return min(100, score)


def analyze(text: str) -> dict:
    sentences = split_sentences(text)
    words = re.findall(r'\b\w+\b', text.lower())

    cit = detect_citations(text)
    bor = detect_borrowing(text)
    ai  = detect_ai(text)

    # Originality = remainder after removing ai, borrowing, citation portions
    # Each score is 0–100 representing % likelihood, not absolute share
    # Combine into approximate shares
    ai_share  = ai["score"]
    cit_share = cit["score"]
    bor_share = bor["score"]

    # Normalize so they don't exceed 100 total
    total = ai_share + cit_share + bor_share
    if total > 100:
        factor = 100 / total
        ai_share  = round(ai_share  * factor)
        cit_share = round(cit_share * factor)
        bor_share = round(bor_share * factor)
        total = ai_share + cit_share + bor_share

    orig_share = max(0, 100 - total)

    # Stats
    avg_sent = (sum(len(s.split()) for s in sentences) / len(sentences)) if sentences else 0

    # Per-sentence AI scores for highlighting
    sentence_scores = [
        {"text": s, "ai_score": score_sentence(s)}
        for s in sentences
    ]

    return {
        "originality": orig_share,
        "borrowing":   bor_share,
        "citation":    cit_share,
        "ai":          ai_share,
        "stats": {
            "chars":       len(text),
            "words":       len(words),
            "sentences":   len(sentences),
            "unique_words": len(set(words)),
            "avg_sent_len": round(avg_sent, 1),
        },
        "details": {
            "ai_phrases":     ai["found_phrases"],
            "borrow_phrases": bor["found"],
            "cited_quotes":   cit["found"],
            "quotes_count":   cit["quotes_count"],
            "refs_count":     cit["refs_count"],
        },
        "sentence_scores": sentence_scores,
    }


def rewrite(text: str) -> dict:
    """Replace AI phrases with human alternatives."""
    result = text
    changes = []
    lower = text.lower()

    for phrase, alts in REWRITES.items():
        if phrase in lower:
            idx = lower.find(phrase)
            original = text[idx: idx + len(phrase)]
            replacement = alts[0]
            # Preserve capitalisation
            if original[0].isupper():
                replacement = replacement[0].upper() + replacement[1:]
            result = result[:idx] + replacement + result[idx + len(phrase):]
            lower = result.lower()
            changes.append({"from": original, "to": replacement, "alts": alts[1:]})

    return {"rewritten": result, "changes": changes}
