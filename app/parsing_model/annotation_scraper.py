import json
import re
import sys
from difflib import SequenceMatcher

import requests
from bs4 import BeautifulSoup

from app.parsing_model.torch_model import preprocess_text


def fetch_html(url):
    """Fetch HTML from a URL with appropriate headers."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "nl-NL,nl;q=0.9",
    }
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    return response.text


def format_jsonld(json_data):
    """Format JSON-LD recipe data into a standardized structure."""
    formatted = {}

    def tokens_to_line(tokens):
        return " ".join(tokens).strip()

    def coerce_text(value):
        if isinstance(value, str):
            return value.strip()
        if value is None:
            return ""
        if isinstance(value, list):
            return " ".join([str(v) for v in value if v]).strip()
        return str(value).strip()

    def first_line(text_value):
        lines = preprocess_text([text_value])
        return tokens_to_line(lines[0]) if lines else ""

    # TITLE
    title_raw = json_data.get("name")
    formatted["title"] = first_line(coerce_text(title_raw))

    # DESCRIPTION
    desc_raw = json_data.get("description")
    formatted["description"] = [
        tokens_to_line(line) for line in preprocess_text([coerce_text(desc_raw)])
    ]

    # INGREDIENTS
    ingredients_raw = json_data.get("recipeIngredient") or []
    if not isinstance(ingredients_raw, list):
        ingredients_raw = [ingredients_raw]
    ingredients_list = [str(ing) for ing in ingredients_raw if ing]
    formatted["ingredients"] = [
        tokens_to_line(line) for line in preprocess_text(ingredients_list)
    ]

    # INSTRUCTIONS
    instr_raw = json_data.get("recipeInstructions") or []
    instructions = []
    if isinstance(instr_raw, dict):
        instr_raw = [instr_raw]
    if isinstance(instr_raw, str):
        instr_raw = [instr_raw]
    for instr in instr_raw:
        if isinstance(instr, dict) and instr.get("text"):
            instr_text = coerce_text(instr.get("text"))
            # Preprocess each instruction and convert token lists to strings
            for line in preprocess_text([instr_text]):
                instructions.append(tokens_to_line(line))
        elif isinstance(instr, str):
            instr_text = coerce_text(instr)
            # Preprocess each instruction and convert token lists to strings
            for line in preprocess_text([instr_text]):
                instructions.append(tokens_to_line(line))
    formatted["instructions"] = [i for i in instructions if i]

    # SERVINGS
    formatted["servings"] = [
        "__number__ personen",
        "__number__ porties",
        "aantal personen __number__",
        "voor __number__ personen",
        "voor __number__ porties",
    ]

    # TIME
    formatted["time"] = [
        "__number__ min.",
        "__number__ minuten",
        "__number__ uur",
        "__number__ min. bereiden",
        "__number__ min. wachten",
        "__number__ min. rusten",
        "__number__ min. oventijd",
        "totale tijd __number__ min.",
        "bereidingstijd __number__",
        "__number__ min. bakken",
        "__number__ min. in de oven",
    ]

    return formatted


def flatten_and_extract_jsonld(html):
    soup = BeautifulSoup(html, "html.parser")

    json_data = {}
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)  # type: ignore[arg-type]
            if isinstance(data, dict) and data.get("@type") == "Recipe":
                json_data = format_jsonld(data)
                break
            elif isinstance(data, list):
                for entry in data:
                    if isinstance(entry, dict) and entry.get("@type") == "Recipe":
                        json_data = format_jsonld(entry)
                        break
        except Exception as e:
            print(f"Error parsing JSON-LD: {e}", file=sys.stderr)

    for tag in soup.find_all(
        [
            "head",
            "header",
            "footer",
            "nav",
            "aside",
            "script",
            "style",
            "noscript",
            "next-route-announcer",
            "iframe",
            "button",
            "a",
            "form",
            "meta",
            "img",
            "svg",
            "video",
            "picture",
            "figure",
            "figcaption",
            "link",
        ]
    ):
        tag.decompose()

    # Also remove elements with header/footer classes or ids
    pattern_list = [
        "footer",
        "site-header",
        "site-footer",
        "related",
        "gerelateerd",
        "nutrition",
        "energy",
        "energie",
        "voedingswaarde",
        "rating",
        "score",
        "review",
        "image",
        "logo",
    ]
    pattern = r"(" + "|".join(pattern_list) + r")"
    for tag in soup.find_all(True):
        attrs = tag.attrs or {}
        class_attr = " ".join(attrs.get("class", [])) if attrs.get("class") else ""
        tag_id = attrs.get("id", "") or ""
        if re.search(pattern, class_attr, re.I):
            tag.decompose()
            continue
        if re.search(pattern, tag_id, re.I):  # type: ignore
            tag.decompose()

    def is_trivial_text_div(tag):
        if tag.name != "div":
            return False

        direct_text = "".join(
            t for t in tag.find_all(string=True, recursive=False)
        ).strip()

        return direct_text.isdigit() and len(direct_text) <= 3

    for div in soup.find_all("div"):
        if is_trivial_text_div(div):
            div.decompose()
            continue
        attrs = div.attrs or {}
        class_attrs = " ".join(attrs.get("class", [])) if attrs.get("class") else ""
        if re.search(r"-details-", class_attrs, re.I):
            div.decompose()
            continue

    # Collapse whitespace to single spaces
    blocks = []
    block_tags = {
        "div",
        "p",
        "ul",
        "ol",
        "li",
        "section",
        "article",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
    }

    def get_text_excluding_nested_blocks(elem):
        """Get text from element but stop at nested block-level elements."""
        texts = []
        for child in elem.children:
            if isinstance(child, str):
                texts.append(child)
            elif child.name not in block_tags:
                # Inline element, get its text recursively
                texts.append(child.get_text(" "))
        return " ".join(texts).strip()

    for elem in soup.find_all(["p", "span", "li", "h1", "h2", "h3", "h4", "h5", "h6"]):
        direct_text = "".join(
            t for t in elem.find_all(string=True, recursive=False)
        ).strip()

        # Skip wrapper elements only if they have no direct text AND no formatting children
        if not direct_text:
            # Check if element has formatting children (b, strong, em, i, u, etc.)
            has_formatting = elem.find(
                [
                    "b",
                    "strong",
                    "em",
                    "i",
                    "u",
                    "mark",
                    "small",
                    "del",
                    "ins",
                    "sub",
                    "sup",
                ]
            )
            if not has_formatting:
                continue

        # Get text but exclude nested block elements
        text = get_text_excluding_nested_blocks(elem)
        text = re.sub(r"\s+", " ", text)
        if len(text) >= 1:
            blocks.append(text)

    # Deduplicate: remove blocks that are substrings of other blocks
    unique_blocks = []
    seen = []
    for block in blocks:
        for existing in seen[::-1]:
            if block in existing or len(block.split()) < 1:
                break
        else:
            unique_blocks.append(block)
            seen.append(block)

    processed_lines = preprocess_text(unique_blocks)

    return processed_lines, apply_json(processed_lines, json_data)


""" incoming JSON-LD example:
{
    "@type": "Recipe",
    "name": "Spicy kippenvleugels uit de airfryer met cottage-cheesedip",
    "alternateName": "",
    "totalTime": "PT50M",
    "description": "Deze spicy kippenvleugels wil iedereen proeven. Logisch, want ze zijn gezond en hebben zó veel smaak. Lekker met een romige cottage-cheesedip en bleekselderij on the side.",
    "recipeYield": "10",
    "recipeIngredient": [
        "600 g scharrel kippenvleugels",
        "2 el milde olijfolie",
        "3 tl piri piri-kruiden",
        "1 tl gerookte paprikapoeder hot",
        "4 stengels bleekselderij",
        "200 g cottagecheese",
        "1 el gedroogde bieslook",
        "1 el gedroogde peterselie",
        "1 tl uienpoeder"
    ],
    "recipeInstructions": [
        {
            "@type": "HowToStep",
            "position": 1,
            "name": "stap 1",
            "text": "Halveer de kippenvleugels."
        },
        {
            "@type": "HowToStep",
            "position": 2,
            "name": "stap 2",
            "text": "Meng de kip met de olie, piripiri-kruiden, paprikapoeder en peper en bak 20 min. op 180 °C in de airfryer."
        },
        {
            "@type": "HowToStep",
            "position": 3,
            "name": "stap 3",
            "text": "Keer de kippenvleugels en bak nog 7-10 min. op 200 °C."
        }
    ],
}
"""


def apply_json(text: list[list[str]], json_data: dict[str, str]):
    """Reformat JSON-LD recipe data into a standardized structure using similarity scoring.
    output structure:
    [
        {line: label},
        ...
    ]
    """

    def normalize_for_similarity(s: str) -> str:
        """Normalize string for similarity comparison, treating __number__ as single character."""
        return s.replace("__number__", "_")

    def similarity(a: str, b: str) -> float:
        """Calculate character-level similarity between two strings."""
        a_norm = normalize_for_similarity(a.lower())
        b_norm = normalize_for_similarity(b.lower())
        return SequenceMatcher(None, a_norm, b_norm).ratio()

    annotated = []

    flattened = []
    for value in json_data.values():
        if isinstance(value, str):
            flattened.append(value)
        elif isinstance(value, list):
            flattened.extend(value)

    for idx, line in enumerate(text):
        line_str = " ".join(line)
        line_lower = line_str.strip().lower()
        scores = {}

        # Calculate similarity for title
        if "title" in json_data and json_data["title"]:
            title_clean = json_data["title"].strip().lower()
            score = similarity(line_lower, title_clean)
            scores["title"] = score

        # Calculate max similarity for servings (now a list)
        if "servings" in json_data and json_data["servings"]:
            servings_list = (
                json_data["servings"]
                if isinstance(json_data["servings"], list)
                else [json_data["servings"]]
            )
            max_score = 0.0
            for servings in servings_list:
                servings_clean = str(servings).strip().lower()
                score = similarity(line_lower, servings_clean)
                if score > max_score:
                    max_score = score
            scores["servings"] = max_score

        # Calculate max similarity for time (now a list)
        if "time" in json_data and json_data["time"]:
            time_list = (
                json_data["time"]
                if isinstance(json_data["time"], list)
                else [json_data["time"]]
            )
            max_score = 0.0
            for time_str in time_list:
                time_clean = str(time_str).strip().lower()
                score = similarity(line_lower, time_clean)
                if score > max_score:
                    max_score = score
            scores["time"] = max_score

        # Calculate max similarity for description
        if "description" in json_data and json_data["description"]:
            desc_list = (
                json_data["description"]
                if isinstance(json_data["description"], list)
                else [json_data["description"]]
            )
            max_score = 0.0
            for desc in desc_list:
                desc_clean = desc.strip().lower()
                score = similarity(line_lower, desc_clean)
                if score > max_score:
                    max_score = score
            scores["description"] = max_score

        # Calculate max similarity for ingredients
        if "ingredients" in json_data and json_data["ingredients"]:
            ing_list = (
                json_data["ingredients"]
                if isinstance(json_data["ingredients"], list)
                else [json_data["ingredients"]]
            )
            max_score = 0.0
            for ing in ing_list:
                ing_clean = ing.strip().lower()
                score = similarity(line_lower, ing_clean)
                if score > max_score:
                    max_score = score
            scores["ingredients"] = max_score

        # Calculate max similarity for instructions
        if "instructions" in json_data and json_data["instructions"]:
            instr_list = (
                json_data["instructions"]
                if isinstance(json_data["instructions"], list)
                else [json_data["instructions"]]
            )
            max_score = 0.0
            for instr in instr_list:
                instr_clean = instr.strip().lower()
                score = similarity(line_lower, instr_clean)
                if score > max_score:
                    max_score = score
            scores["instructions"] = max_score

        # Select label with highest score
        if scores:
            scores = {k: round(v, 3) for k, v in scores.items() if v > 0.0}
            label = max(scores, key=lambda k: scores[k])  # type: ignore
            best_score = scores[label]
            # Apply "other" label if highest score is below 75%
            if best_score < 0.75:
                label = "other"
        else:
            label = "other"

        annotated.append({line_str: label})
    return annotated


if __name__ == "__main__":
    for url in sys.stdin:
        html = fetch_html(url.strip())
        text, annotated = flatten_and_extract_jsonld(html)
        print(json.dumps(annotated, ensure_ascii=False, indent=2))
