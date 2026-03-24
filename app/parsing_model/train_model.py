import torch
import torch.nn as nn

from app.parsing_model.torch_model import (
    ID_TO_LABEL,
    LABEL_TO_ID,
    LABELS,
    RecipeSequenceTagger,
    build_vocab,
    encode_lines,
)


def train(recipes, labels):
    embedding_dim = 128
    hidden_dim = 64
    max_tokens = 20

    vocab = build_vocab(recipes)

    model = RecipeSequenceTagger(
        vocab_size=len(vocab),
        embedding_dim=embedding_dim,
        hidden_dim=hidden_dim,
        num_labels=len(LABELS),
    )

    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    loss_fn = nn.CrossEntropyLoss()

    for epoch in range(10):
        for recipe, recipe_labels in zip(recipes, labels):
            token_ids, mask = encode_lines(recipe, vocab, max_tokens)
            targets = torch.tensor(recipe_labels)
            logits = model(token_ids, mask)
            loss = loss_fn(logits, targets)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

    torch.save(
        {
            "model_state": model.state_dict(),
            "vocab": vocab,
            "label_to_id": LABEL_TO_ID,
            "id_to_label": ID_TO_LABEL,
            "config": {
                "embedding_dim": embedding_dim,
                "hidden_dim": hidden_dim,
                "max_tokens": max_tokens,
            },
        },
        "recipe_tagger.pt",
    )
