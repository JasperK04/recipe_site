"""
Parse recipe information from various document formats (PDF, DOCX, TXT, etc.).
Uses pattern matching and heuristics to extract structured recipe data.

This parser uses rule-based extraction to identify:
- Recipe title (from first meaningful line)
- Ingredients section (keywords: ingredient, ingrediënt, benodigdheden)
- Instructions section (keywords: instruction, bereiding, preparation, stappen)
- Time values (prep, cook, oven times from patterns like "15 min")
- Servings (patterns like "serves 4" or "4 porties")
- Ingredient quantities and measurements (patterns like "200 g flour")

The parser works best with well-structured recipe documents that have clear
section headers and formatted ingredient lists.
"""

import os
import re
from typing import Any


def extract_text_from_pdf(file_path: str) -> str:
    """Extract text content from a PDF file."""
    try:
        import PyPDF2

        text = ""
        with open(file_path, "rb") as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
        return text.strip()
    except ImportError:
        raise ImportError(
            "PyPDF2 is required to parse PDF files. Install it with: pip install PyPDF2"
        )


def extract_text_from_docx(file_path: str) -> str:
    """Extract text content from a DOCX file."""
    try:
        from docx import Document

        doc = Document(file_path)
        text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
        return text.strip()
    except ImportError:
        raise ImportError(
            "python-docx is required to parse DOCX files. Install it with: pip install python-docx"
        )


def extract_text_from_txt(file_path: str) -> str:
    """Extract text content from a plain text file."""
    with open(file_path, "r", encoding="utf-8", errors="ignore") as file:
        return file.read().strip()


def extract_text_from_file(file_path: str) -> str:
    """Extract text from various file formats."""
    _, ext = os.path.splitext(file_path.lower())

    if ext == ".pdf":
        return extract_text_from_pdf(file_path)
    elif ext in [".docx", ".doc"]:
        return extract_text_from_docx(file_path)
    elif ext == ".txt":
        return extract_text_from_txt(file_path)
    else:
        # Try to read as text for unknown formats
        try:
            return extract_text_from_txt(file_path)
        except Exception:
            raise ValueError(
                f"Unsupported file format: {ext}. Supported formats: PDF, DOCX, TXT"
            )


def _extract_title(lines: list[str]) -> str:
    """Extract recipe title from text lines."""
    # Title is usually in the first few lines, often the longest or most prominent
    for line in lines:
        line = line.strip()
        if len(line) > 25 and len(line) < 100 and not line.endswith(":"):
            return line
    return "Untitled Recipe"


def _extract_servings(text: str) -> int | None:
    """Extract number of servings from text."""
    # Prefer line-based patterns now that preprocessing puts items on separate lines
    line_patterns = [
        r"^(\d+)\s*(?:pers(?:oon)?|personen|porties?|portion|portions?|pax|p)\b",
        r"^voor\s+(\d+)\s+(?:pers(?:oon)?|personen|people)\b",
    ]

    for line in text.split("\n"):
        for pattern in line_patterns:
            match = re.search(pattern, line.strip(), re.IGNORECASE)
            if match:
                return int(match.group(1))

    # Fallback to legacy patterns
    patterns = [
        r"(?:serves?|servings?|porties?|portions?)[:\s]+(\d+)",
        r"(\d+)\s+(?:servings?|porties?|portions?)",
        r"voor\s+(\d+)\s+(?:personen|people)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def _extract_time(text: str, time_type: str) -> int | None:
    """Extract time in minutes from text for specific time type."""
    keywords = {
        "prep": ["prep", "voorbereiding", "voorbereiden", "preparation"],
        "cook": ["cook", "bereiding", "bereiden", "cooking"],
        "oven": ["oven", "baking", "bakken"],
    }

    type_keywords = keywords.get(time_type, [])

    for keyword in type_keywords:
        # Look for patterns like "prep time: 15 minutes" or "15 min prep"
        patterns = [
            rf"{keyword}[:\s]+(\d+)\s*(?:min|minuten|minutes)",
            rf"(\d+)\s*(?:min|minuten|minutes)\s+{keyword}",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return int(match.group(1))
    return None


def _split_into_sections(text: str) -> dict[str, str]:
    """Split text into logical sections (ingredients, instructions, etc.)."""
    sections = {"ingredients": "", "instructions": ""}

    # Normalize text
    text = text.replace("\r\n", "\n")
    lines = text.split("\n")

    current_section = None
    section_content = []

    for line in lines:
        line_lower = line.lower().strip()

        # Detect section headers
        if any(
            keyword in line_lower
            for keyword in [
                "ingredient",
                "ingredienten",
                "ingrediënt",
                "ingrediënten",
                "benodigdheden",
            ]
        ):
            if current_section and section_content:
                sections[current_section] = "\n".join(section_content)
            current_section = "ingredients"
            section_content = []
        elif any(
            keyword in line_lower
            for keyword in [
                "instruction",
                "direction",
                "bereiding",
                "bereidingswijze",
                "preparation",
                "method",
                "werkwijze",
                "stappen",
                "steps",
            ]
        ):
            if current_section and section_content:
                sections[current_section] = "\n".join(section_content)
            current_section = "instructions"
            section_content = []
        elif current_section:
            section_content.append(line)

    # Save last section
    if current_section and section_content:
        sections[current_section] = "\n".join(section_content)

    return sections


def _split_lines(text: str, split_on_numbers: bool = False) -> list[str]:
    """
    Preprocess text and split into lines based on capitalization, periods, and optionally numbers.

    Preprocessing rules:
    1. Normalize fraction characters (½, ¼, etc.) to decimal numbers
    2. Remove all existing newlines (collapse to spaces)
    3. Add newlines after periods (.)
    4. Add newlines before any capital letter (even within words like "GoTo" -> "Go\nTo")
    5. Add newlines before any number if split_on_numbers is True
    """
    # Step 0: Normalize fractions to decimals
    fraction_map = {
        "¼": " 0.25 ",
        "½": " 0.5 ",
        "¾": " 0.75 ",
        "⅓": " 0.333 ",
        "⅔": " 0.667 ",
        "⅛": " 0.125 ",
    }
    for fraction, decimal in fraction_map.items():
        text = text.replace(fraction, decimal)

    # Preprocessing step: normalize line breaks
    # Step 1: Remove all existing newlines and normalize whitespace
    text = re.sub(r"\s+", " ", text)

    # Step 2: Temporarily replace floats with placeholders to protect them
    # Match patterns like 0.5, 123.456, etc.
    float_pattern = r"\d+\.\d+"
    floats = re.findall(float_pattern, text)
    float_map = {}
    for i, float_val in enumerate(floats):
        placeholder = f"__FLOAT_{i}__"
        float_map[placeholder] = float_val
        text = text.replace(float_val, placeholder, 1)

    # Step 3: Add newline after periods followed by space or end of string
    text = re.sub(r"\.\s+", ".\n", text)
    text = re.sub(r"\.$", ".\n", text)

    # Step 4: Restore floats from placeholders
    for placeholder, float_val in float_map.items():
        text = text.replace(placeholder, float_val)

    # Step 5: Add newlines before capital letters (including within words)
    # Use a negative lookbehind to avoid adding newline at the start of string
    text = re.sub(r"(?<!^)([A-Z])", r"\n\1", text)

    # Step 6: Add newlines before numbers (only if split_on_numbers is True)
    # But first protect floats again since they were restored in Step 4
    floats_second = re.findall(float_pattern, text)
    float_map_second = {}
    for i, float_val in enumerate(floats_second):
        placeholder = f"__FLOAT__{''.join('I' for _ in range(i))}__"
        float_map_second[placeholder] = float_val
        text = text.replace(float_val, placeholder, 1)

    # Now safely split on numbers without breaking floats
    if split_on_numbers:
        text = re.sub(r"(?<!\d)(?<![,.])\s*(\d)", r"\n\1", text)

    # Restore floats from placeholders again

    # Clean up multiple consecutive newlines
    text = re.sub(r"\n+", "\n", text)
    text = text.strip()

    # Splitting step: split based on capitalization and periods
    # When split_on_numbers=True: split before numbers but NOT after (to keep numbers with following text)
    # When split_on_numbers=False: only split on capitalization and periods
    # Note: Use (?<![0-9.]) to avoid splitting floats like 0.5 (don't split before digit if preceded by . or digit)
    # Also split before float placeholders (__FLOAT__)
    if split_on_numbers:
        pattern = r"(?<=[a-z])(?=[A-Z])|(?<=[.])(?=\S)|(?<![0-9.])(?=\d)|(?=__FLOAT)"
    else:
        pattern = r"(?<=[a-z])(?=[A-Z])|(?<=[.])(?=\S)|(?=__FLOAT)"

    # Split the text based on the pattern
    intermediate = [
        segment.strip() for segment in re.split(pattern, text) if segment.strip()
    ]

    # Restore floats from placeholders again
    final_lines = []
    for segment in intermediate:
        for placeholder, float_val in float_map_second.items():
            segment = segment.replace(placeholder, float_val)
        final_lines.append(segment.strip())

    return final_lines


def _split_sections(text: str) -> tuple[str, str]:
    """
    Split the document into two main parts at "bereidingswijze" keyword.

    Returns:
        Tuple of (before_bereiding, after_bereiding) where:
        - before_bereiding: Everything before "bereidingswijze" (contains head + ingredients)
        - after_bereiding: Everything after "bereidingswijze" (contains prep steps + footer)

    These are returned without preprocessing to allow selective preprocessing.
    """
    # Find the "bereidingswijze" keyword (or similar: bereiding, bereidingsweize, etc.)
    bereiding_keywords = [
        "bereidingswijze",
        "bereidingsweize",
        "bereiding",
        "preparation method",
        "werkwijze",
    ]

    text_lower = text.lower()
    split_pos = None
    keyword_found = None

    # Find all keyword occurrences and pick the earliest position with the longest keyword
    for keyword in bereiding_keywords:
        pos = text_lower.find(keyword)
        if pos != -1:
            # If same position, prefer the longer keyword
            if (
                split_pos is None
                or pos < split_pos
                or (
                    pos == split_pos
                    and keyword_found is not None
                    and len(keyword) > len(keyword_found)
                )
            ):
                split_pos = pos
                keyword_found = keyword

    # Split at the keyword position
    if split_pos is not None and keyword_found is not None:
        before_bereiding = text[:split_pos].strip()
        # Skip the keyword itself and start the after part
        after_bereiding = text[split_pos + len(keyword_found) :].strip()
    else:
        before_bereiding = text.strip()
        after_bereiding = ""

    return before_bereiding, after_bereiding


def _split_before_section(text: str) -> tuple[str, str]:
    """
    Split the "before bereiding" section into head and ingredients.

    Returns:
        Tuple of (head, ingredients) where:
        - head: Everything before "ingredienten" keyword (document header)
        - ingredients: Everything after "ingredienten" keyword
    """
    # Find the "ingredienten" keyword (or similar)
    ingredient_keywords = [
        "ingredienten",
        "ingrediënt",
        "ingrediënten",
        "ingredient",
        "benodigdheden",
        "ingredients",
    ]

    text_lower = text.lower()
    split_pos = None
    keyword_found = None

    # Find all keyword occurrences and pick the earliest position with the longest keyword
    for keyword in ingredient_keywords:
        pos = text_lower.find(keyword)
        if pos != -1:
            # If same position, prefer the longer keyword
            if (
                split_pos is None
                or pos < split_pos
                or (
                    pos == split_pos
                    and keyword_found is not None
                    and len(keyword) > len(keyword_found)
                )
            ):
                split_pos = pos
                keyword_found = keyword

    # Split at the keyword position
    if split_pos is not None and keyword_found is not None:
        head = text[:split_pos].strip()
        # Skip the keyword itself and start the ingredients part
        ingredients = text[split_pos + len(keyword_found) :].strip()
    else:
        # No ingredient keyword found, all is head
        head = text.strip()
        ingredients = ""

    return head, ingredients


def _split_after_section(text: str) -> tuple[str, str]:
    """
    Split the "after bereiding" section into footer and instructions.

    Returns:
        Tuple of (footer, instructions) where:
        - footer: Everything after the "instructies" section
        - instructions: Everything inside "instructies" section
    """
    # Find the "ingredienten" keyword (or similar)
    ingredient_keywords = ["\n\n"]
    text_lower = text.lower()
    split_pos = None
    keyword_found = None

    # Find all keyword occurrences and pick the earliest position with the longest keyword
    for keyword in ingredient_keywords:
        pos = text_lower.find(keyword)
        if pos != -1:
            # If same position, prefer the longer keyword
            if (
                split_pos is None
                or pos < split_pos
                or (
                    pos == split_pos
                    and keyword_found is not None
                    and len(keyword) > len(keyword_found)
                )
            ):
                split_pos = pos
                keyword_found = keyword

    # Split at the keyword position
    if split_pos is not None and keyword_found is not None:
        head = text[:split_pos].strip()
        # Skip the keyword itself and start the ingredients part
        ingredients = text[split_pos + len(keyword_found) :].strip()
    else:
        # No ingredient keyword found, all is head
        head = text.strip()
        ingredients = ""

    return head, ingredients


def _parse_ingredients(text: str) -> list[dict[str, Any]]:
    """Parse ingredients from text section."""
    ingredients = []
    lines = [line.strip() for line in text.split("\n") if line.strip()]

    # Common measurement units
    measurements = (
        r"(?:g|kg|ml|l|el|tl|gram|kilo|liter|stuks?|st|tbsp|tsp|cup|cups|ounce|oz)"
    )

    for line in lines:
        # Skip section headers and very short lines
        if len(line) < 3 or ":" in line[:20]:
            continue

        # Pattern 1: number + measurement unit + name (e.g., "200 g flour")
        pattern_with_unit = rf"^(\d+(?:[.,]\d+)?)\s+({measurements})\s+(.*)$"
        match = re.match(pattern_with_unit, line, re.IGNORECASE)

        if match:
            qty_str, measurement, name = match.groups()
            try:
                qty = float(qty_str.replace(",", "."))
            except Exception:
                qty = qty_str
            measurement = (measurement or "stuks").lower()

            print(
                f"Parsed ingredient - Name: {name}, Quantity: {qty}, Measurement: {measurement}"
            )

            # Normalize measurements
            measurement_map = {
                "gram": "g",
                "kilo": "kg",
                "liter": "l",
                "st": "stuks",
                "tbsp": "el",
                "tsp": "tl",
                "cup": "stuks",
                "cups": "stuks",
                "ounce": "g",
                "oz": "g",
            }
            measurement = measurement_map.get(measurement, measurement)

            ingredients.append(
                {
                    "name_": name.strip(),
                    "quantity": qty,
                    "measurement": measurement,
                }
            )
        else:
            # Pattern 2: number + name (no unit, e.g., "1 rijpe banaan")
            pattern_without_unit = r"^(\d+(?:[.,]\d+)?)\s+(.+)$"
            match_no_unit = re.match(pattern_without_unit, line, re.IGNORECASE)

            if match_no_unit:
                qty_str, name = match_no_unit.groups()
                try:
                    qty = float(qty_str.replace(",", "."))
                except Exception:
                    qty = qty_str

                ingredients.append(
                    {
                        "name_": name.strip(),
                        "quantity": qty,
                        "measurement": "stuks",
                    }
                )
            else:
                # Fallback: Treat the entire line as the ingredient name
                ingredients.append(
                    {"name_": line, "quantity": None, "measurement": None}
                )

    return ingredients


def _parse_instructions(text: str) -> list[str]:
    """Parse instructions from text section."""
    instructions = []
    lines = [line.strip() for line in text.split("\n") if line.strip()]

    for line in lines:
        # Skip obvious section headers
        if any(
            kw in line.lower()
            for kw in [
                "bereiding",
                "bereidingswijze",
                "bereidingsweize",
                "stappen",
                "steps",
                "instructions",
            ]
        ):
            continue

        # Remove numbered prefixes like "1.", "Step 1:", etc.
        line = re.sub(
            r"^(?:\d+\.|\d+\)|step\s+\d+:?)\s*", "", line, flags=re.IGNORECASE
        )

        if line:
            instructions.append(line)

    return instructions


def parse_recipe_with_patterns(text: str) -> dict[str, Any]:
    """
    Parse recipe information from text using pattern matching and heuristics.
    Returns a structured dictionary with recipe data.
    """
    lines = [line.strip() for line in text.split("\n") if line.strip()]

    # Extract title
    title = _extract_title(lines)

    # Extract metadata
    servings = _extract_servings(text)
    prep_time = _extract_time(text, "prep")
    cook_time = _extract_time(text, "cook")
    oven_time = _extract_time(text, "oven")

    # Split into sections
    sections = _split_into_sections(text)

    # Parse ingredients and instructions
    ingredients = _parse_ingredients(sections.get("ingredients", ""))
    instructions = _parse_instructions(sections.get("instructions", ""))

    # Fallback: infer sections from line order when headers are missing
    instruction_keywords = [
        "instruction",
        "direction",
        "bereiding",
        "bereidingswijze",
        "bereidingsweize",
        "preparation",
        "method",
        "werkwijze",
        "stappen",
        "steps",
    ]

    # Locate first instruction header line
    instruction_start = None
    for idx, line in enumerate(lines):
        if any(kw in line.lower() for kw in instruction_keywords):
            instruction_start = idx + 1  # steps start after header
            break

    # Ingredient-like line matcher: matches lines starting with number (with or without measurement)
    # Examples: "80 g winterpeen", "1 rijpe banaan", "2 el zonnebloemolie"
    ingredient_line_re = re.compile(r"^\d+(?:[.,]\d+)?(?:\s+\S+)?\s+.+$")

    # If ingredients are empty, try leading block of ingredient-like lines after the title
    if not ingredients:
        leading_ing: list[str] = []
        remaining: list[str] = []
        for idx, line in enumerate(lines[1:], start=1):  # skip title
            if ingredient_line_re.match(line):
                leading_ing.append(line)
            else:
                remaining = lines[idx:]  # start instructions from this line onwards
                break
        if leading_ing:
            ingredients = _parse_ingredients("\n".join(leading_ing))
        if not instructions and remaining:
            instructions = _parse_instructions("\n".join(remaining))

    # If instructions still empty but we found an instruction header, parse from there
    if not instructions and instruction_start is not None:
        instructions = _parse_instructions("\n".join(lines[instruction_start:]))

    # Try to extract a description (first paragraph that's not title or section)
    description = ""
    for line in lines[1:5]:
        if len(line) > 20 and len(line) < 500 and ":" not in line:
            description = line[:500]
            break

    return {
        "title": title,
        "description": description,
        "ingredients": ingredients,
        "instructions": instructions,
        "prep_time": prep_time,
        "cook_time": cook_time,
        "oven_time": oven_time,
        "servings": servings,
        "category": None,  # Category detection is tricky without AI
    }


def parse_recipe_with_sections(text: str) -> dict[str, Any]:
    """Parse a recipe document into structured sections with selective preprocessing."""
    # Step 1: Split on bereidingswijze to get before and after parts
    first, second = _split_sections(text)

    # Step 2: Split before part into head and ingredients
    head, ingredients_text = _split_before_section(first)

    instructions_text, footer = _split_after_section(second)

    # Step 3: Preprocess and split head section (do NOT split on numbers, like footer)
    head_lines = _split_lines(head, split_on_numbers=False)

    # Step 4: Preprocess and split ingredient section (split on numbers)
    ingredients_lines = _split_lines(ingredients_text, split_on_numbers=True)

    # Step 5: Preprocess and split prep section (do NOT split on numbers)
    instructions_lines = _split_lines(instructions_text, split_on_numbers=False)

    # Step 6: Combine footer back to head if needed
    footer_lines = _split_lines(footer, split_on_numbers=False)

    # Step 7: Parse ingredients and instructions
    head_preprocessed_str = "\n".join(head_lines)
    ingredients_preprocessed_str = "\n".join(ingredients_lines)
    instructions_preprocessed_str = "\n".join(instructions_lines)
    footer_preprocessed_str = "\n".join(footer_lines)

    ingredients = _parse_ingredients(ingredients_preprocessed_str)
    instructions = _parse_instructions(instructions_preprocessed_str)

    return {
        "head": head_preprocessed_str,
        "ingredients_preprocessed": ingredients_preprocessed_str,
        "instructions_preprocessed": instructions_preprocessed_str,
        "ingredients": ingredients,
        "instructions": instructions,
        "footer": footer_preprocessed_str,
    }


def parse_document(file_path: str) -> dict[str, Any]:
    """
    Parse a document file and extract recipe information.

    Args:
        file_path: Path to the document file (PDF, DOCX, TXT, etc.)

    Returns:
        Dictionary with recipe data compatible with RecipeForm:
        - title: str
        - description: str
        - ingredients: list[dict] with name_, quantity, measurement
        - instructions: list[str]
        - prep_time: int or None
        - cook_time: int or None
        - oven_time: int or None
        - servings: int or None
        - category: str or None
    """
    # Step 1: Extract text from the document
    text = extract_text_from_file(file_path)

    if not text or len(text.strip()) < 10:
        raise ValueError(
            "Document appears to be empty or contains insufficient text to parse."
        )

    # Step 2: Split on bereidingswijze to get before and after parts
    first, second = _split_sections(text)

    # Step 3: Split before part into head and ingredients
    head, ingredients_raw = _split_before_section(first)

    instructions_raw, footer = _split_after_section(second)

    # Step 4: Preprocess and split head section (do NOT split on numbers)
    head_preprocessed_list = _split_lines(head, split_on_numbers=False)
    head_preprocessed = "\n".join(head_preprocessed_list)

    # Step 5: Preprocess and split ingredient section (split on numbers)
    ingredients_preprocessed_list = _split_lines(ingredients_raw, split_on_numbers=True)
    ingredients_preprocessed = "\n".join(ingredients_preprocessed_list)

    # Step 6: Preprocess and split instructions section (do NOT split on numbers)
    instructions_preprocessed_list = _split_lines(
        instructions_raw, split_on_numbers=False
    )
    instructions_preprocessed = "\n".join(instructions_preprocessed_list)

    # Step 7: Parse ingredients and instructions to structured data
    ingredients = _parse_ingredients(ingredients_preprocessed)
    instructions = _parse_instructions(instructions_preprocessed)

    # Step 8: Extract metadata from head section
    head_lines = head_preprocessed.split("\n")
    title = _extract_title(head_lines)
    prep_time = _extract_time(head_preprocessed, "prep")
    cook_time = _extract_time(head_preprocessed, "cook")
    oven_time = _extract_time(head_preprocessed, "oven")

    # Extract servings from head first, then try ingredients as fallback
    servings = _extract_servings(head_preprocessed)
    if servings is None:
        servings = _extract_servings(ingredients_preprocessed)

    # Try to extract description from head (first paragraph that's not title)
    description = ""
    for line in head_lines[1:5]:
        if len(line) > 20 and len(line) < 500 and ":" not in line:
            description = line[:500]
            break

    # Step 9: Normalize ingredients and instructions
    normalized_ingredients = []
    for ing in ingredients:
        if isinstance(ing, dict):
            normalized_ingredients.append(
                {
                    "name_": ing.get("name_", ""),
                    "quantity": ing.get("quantity"),
                    "measurement": ing.get("measurement", ""),
                }
            )

    normalized_instructions = [str(instr) for instr in instructions if instr]

    return {
        "title": title,
        "description": description,
        "ingredients": normalized_ingredients,
        "instructions": normalized_instructions,
        "prep_time": prep_time,
        "cook_time": cook_time,
        "oven_time": oven_time,
        "servings": servings,
        "category": None,
    }


def parse_document_with_debug(file_path: str) -> dict[str, Any]:
    """
    Parse a document file and return all intermediate parsing steps for debugging.

    Args:
        file_path: Path to the document file (PDF, DOCX, TXT, etc.)

    Returns:
        Dictionary with all intermediate steps and final parsed data:
        - raw_text: Original unprocessed text
        - before_bereiding: Text before "bereidingswijze" keyword
        - after_bereiding: Text after "bereidingswijze" keyword
        - head: Document header section
        - ingredients_raw: Raw ingredients text before splitting
        - ingredients_preprocessed: Ingredients after preprocessing and splitting
        - instructions_raw: Raw instructions text before splitting
        - instructions_preprocessed: Instructions after preprocessing and splitting
        - parsed_recipe: Final parsed recipe data
    """
    # Step 1: Extract text from the document
    raw_text = extract_text_from_file(file_path)

    if not raw_text or len(raw_text.strip()) < 10:
        raise ValueError(
            "Document appears to be empty or contains insufficient text to parse."
        )

    # Step 2: Split on bereidingswijze to get before and after parts
    first, second = _split_sections(raw_text)

    # Step 3: Split before part into head and ingredients
    head, ingredients_raw = _split_before_section(first)

    instructions_raw, footer = _split_after_section(second)

    # Step 4: Preprocess and split head section (do NOT split on numbers, like footer)
    head_preprocessed_list = _split_lines(head, split_on_numbers=False)
    head_preprocessed = "\n".join(head_preprocessed_list)

    # Step 5: Preprocess and split ingredient section (split on numbers)
    ingredients_preprocessed_list = _split_lines(ingredients_raw, split_on_numbers=True)
    ingredients_preprocessed = "\n".join(ingredients_preprocessed_list)

    # Step 6: Preprocess and split prep section (do NOT split on numbers)
    instructions_preprocessed_list = _split_lines(
        instructions_raw, split_on_numbers=False
    )
    instructions_preprocessed = "\n".join(instructions_preprocessed_list)

    # Step 7: Preprocess and split footer section (do NOT split on numbers)
    footer_preprocessed_list = _split_lines(footer, split_on_numbers=False)
    footer_preprocessed = "\n".join(footer_preprocessed_list)

    # Step 8: Parse ingredients and instructions to structured data
    ingredients = _parse_ingredients(ingredients_preprocessed)
    instructions = _parse_instructions(instructions_preprocessed)

    # Step 9: Extract metadata from head section
    head_lines = head_preprocessed.split("\n")
    title = _extract_title(head_lines)
    prep_time = _extract_time(head_preprocessed, "prep")
    cook_time = _extract_time(head_preprocessed, "cook")
    oven_time = _extract_time(head_preprocessed, "oven")

    # Extract servings from head first, then try ingredients as fallback
    servings = _extract_servings(head_preprocessed)
    if servings is None:
        servings = _extract_servings(ingredients_preprocessed)

    # Try to extract description from head (first paragraph that's not title)
    description = ""
    for line in head_lines[1:5]:
        if len(line) > 20 and len(line) < 500 and ":" not in line:
            description = line[:500]
            break

    # Step 10: Normalize ingredients and instructions from sections
    normalized_ingredients = []
    for ing in ingredients:
        if isinstance(ing, dict):
            normalized_ingredients.append(
                {
                    "name_": ing.get("name_", ""),
                    "quantity": ing.get("quantity"),
                    "measurement": ing.get("measurement", ""),
                }
            )

    normalized_instructions = [str(instr) for instr in instructions if instr]

    # Return all intermediate steps
    return {
        "raw_text": raw_text,
        "before_bereiding": first,
        "after_bereiding": second,
        "head": head,
        "head_preprocessed": head_preprocessed,
        "ingredients_raw": ingredients_raw,
        "ingredients_preprocessed": ingredients_preprocessed,
        "instructions_raw": instructions_raw,
        "instructions_preprocessed": instructions_preprocessed,
        "footer": footer,
        "footer_preprocessed": footer_preprocessed,
        "parsed_recipe": {
            "title": title,
            "description": description,
            "ingredients": normalized_ingredients,
            "instructions": normalized_instructions,
            "prep_time": prep_time,
            "cook_time": cook_time,
            "oven_time": oven_time,
            "servings": servings,
            "category": None,
        },
    }
