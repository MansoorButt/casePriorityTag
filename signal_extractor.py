
import cohere
import json
import re
from config import COHERE_API_KEY

co = cohere.Client(COHERE_API_KEY)


def extract_signals_with_ai(case_text: str) -> dict:
    snippet = case_text[:3000]

    prompt = f"""
You are a STRICT legal classifier for Pakistani court case files.

Your job is to EXTRACT and INFER missing information.
You MUST NOT return "unknown" unless absolutely impossible.

Rules:
- Always infer case_type from text (use keywords like murder, theft, fraud, etc.)
- Always generate a realistic case_title if not present
- If court not mentioned, assume "Sessions Court"
- If accused name not found, write "Unnamed Accused"
- Do NOT leave important fields empty or unknown

Return ONLY valid JSON.

Case text:
\"\"\"{snippet}\"\"\"

{{
  "case_title": "...",
  "case_type": "murder | terrorism | kidnapping | rape | robbery | fraud | drug | corruption | civil | property",
  "section": "...",
  "court": "...",
  "accused_name": "...",
  "accused_in_custody": true or false,
  "involves_minor": true or false,
  "involves_woman": true or false,
  "involves_elder": true or false,
  "adjournment_count": number,
  "days_waiting": number,
  "summary": "...",
  "urgency_keywords": ["...", "..."]
}}
"""

    response = co.generate(
        model="command",
        prompt=prompt,
        max_tokens=500,
        temperature=0.1,
        stop_sequences=["```"]
    )

    raw = response.generations[0].text.strip()
    raw = re.sub(r"```json|```", "", raw).strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return fallback_extract(case_text)


def fallback_extract(text: str) -> dict:
    text_lower = text.lower()

    type_keywords = {
        "murder":     ["murder", "killed", "homicide", "302", "death"],
        "terrorism":  ["terrorism", "terrorist", "bomb", "ata", "explosive"],
        "kidnapping": ["kidnap", "abduct", "ransom", "365"],
        "rape":       ["rape", "sexual assault", "376"],
        "robbery":    ["robbery", "robbed", "armed", "392"],
        "fraud":      ["fraud", "forgery", "cheating", "420"],
        "drug":       ["narcotics", "heroin", "drug", "cns"],
        "corruption": ["corruption", "bribery", "nab", "embezzl"],
    }

    detected_type = "other"
    for ctype, keywords in type_keywords.items():
        if any(kw in text_lower for kw in keywords):
            detected_type = ctype
            break

    return {
        "case_title":          "Unknown Case",
        "case_type":           detected_type,
        "section":             "unknown",
        "court":               "unknown",
        "accused_name":        "unknown",
        "accused_in_custody":  "custody" in text_lower or "arrested" in text_lower,
        "involves_minor":      "minor" in text_lower or "child" in text_lower,
        "involves_woman":      "woman" in text_lower or "female" in text_lower,
        "involves_elder":      "elderly" in text_lower or "senior" in text_lower,
        "adjournment_count":   text_lower.count("adjourn"),
        "days_waiting":        0,
        "summary":             text[:200],
        "urgency_keywords":    [],
    }
