import re
import unicodedata
from collections import Counter

import torch
import torch.nn as nn

LABELS = [
    "title",
    "description",
    "ingredients",
    "servings",
    "time",
    "instructions",
    "other",
]

LABEL_TO_ID = {l: i for i, l in enumerate(LABELS)}  # noqa: E741
ID_TO_LABEL = {i: l for l, i in LABEL_TO_ID.items()}  # noqa: E741


def preprocess_text(text: list[str]) -> list[list[str]]:
    """Preprocess text into tokenized lines split on '.' (excluding 'min.')."""

    def normalize(text):
        # Handle number ranges first (e.g., "40-45" -> "__number__")
        text = re.sub(r"\d+(?:[.,]\d+)?[\-/]\d+(?:[.,]\d+)?", "__number__", text)
        # Then handle other separators
        text = re.sub(r"[\-/,;:()\[\]{}\"'`\\]+", " ", text)
        text = re.sub(r"[:;,!?]+", ".", text)
        text = re.sub(r"[¼½¾⅓⅔⅛⅕]", "__number__", text)
        text = re.sub(r"\d+(?:[.,]\d+)?", "__number__", text)
        text = re.sub(r"\s+", " ", text)
        text = unicodedata.normalize("NFKD", text)
        return text

    def tokenize_and_split(text):
        lines = []
        current = []
        tokens = text.split()

        for i, tok in enumerate(tokens):
            if tok.lower() in ["min.", "ca."]:
                current.append(tok)
                # Check if next token is capitalized
                if i + 1 < len(tokens) and tokens[i + 1][0].isupper():
                    if current:
                        lines.append(current)
                        current = []
                continue

            if tok.endswith("."):
                base = tok[:-1]
                if base:
                    current.append(base)
                if current:
                    lines.append(current)
                    current = []
                continue

            current.append(tok)

        if current:
            lines.append(current)

        return lines

    tokenized = []
    for line in text:
        line = normalize(line)
        tokenized.extend(tokenize_and_split(line))

    # Merge lines that are just "__number__" with the previous line
    merged = []
    for line in tokenized:
        if line == ["__number__"] and merged:
            merged[-1].extend(line)
        else:
            merged.append(line)

    return merged


def build_vocab(recipes, min_freq=2):
    counter = Counter()
    for recipe in recipes:
        for line in recipe:
            counter.update(line)
    vocab = {"<pad>": 0, "<unk>": 1}
    for word, freq in counter.items():
        if freq >= min_freq:
            vocab[word] = len(vocab)
    return vocab


def encode_lines(lines, vocab, max_tokens):
    token_ids = []
    mask = []
    for line in lines:
        tokens = line[:max_tokens]
        ids = [vocab.get(t, vocab["<unk>"]) for t in tokens]
        padding = max_tokens - len(ids)
        token_ids.append(ids + [0] * padding)
        mask.append([1] * len(ids) + [0] * padding)
    return torch.tensor(token_ids), torch.tensor(mask, dtype=torch.float32)


class RecipeSequenceTagger(nn.Module):
    def __init__(self, vocab_size, embedding_dim, hidden_dim, num_labels):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, embedding_dim, padding_idx=0)
        self.lstm = nn.LSTM(
            embedding_dim, hidden_dim, batch_first=True, bidirectional=True
        )
        self.classifier = nn.Linear(hidden_dim * 2, num_labels)

    def encode_lines(self, token_ids, mask):
        embeddings = self.embedding(token_ids)
        masked = embeddings * mask.unsqueeze(-1)
        summed = masked.sum(dim=1)
        lengths = mask.sum(dim=1).clamp(min=1)
        return summed / lengths.unsqueeze(-1)

    def forward(self, token_ids, mask):
        line_vectors = self.encode_lines(token_ids, mask)
        sequence, _ = self.lstm(line_vectors.unsqueeze(0))
        logits = self.classifier(sequence.squeeze(0))
        return logits
