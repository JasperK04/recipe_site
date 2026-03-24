import torch

from app.parsing_model.torch_model import (
    RecipeSequenceTagger,
    encode_lines,
    preprocess_text,
)


class RecipeTagger:
    def __init__(self, model_path):
        checkpoint = torch.load(model_path, map_location="cpu")

        self.vocab = checkpoint["vocab"]
        self.id_to_label = checkpoint["id_to_label"]
        config = checkpoint["config"]

        self.model = RecipeSequenceTagger(
            vocab_size=len(self.vocab),
            embedding_dim=config["embedding_dim"],
            hidden_dim=config["hidden_dim"],
            num_labels=len(self.id_to_label),
        )

        self.model.load_state_dict(checkpoint["model_state"])
        self.model.eval()
        self.max_tokens = config["max_tokens"]

    def predict(self, text):
        lines = preprocess_text([text])
        token_ids, mask = encode_lines(lines, self.vocab, self.max_tokens)
        with torch.no_grad():
            logits = self.model(token_ids, mask)
        predictions = logits.argmax(dim=-1).tolist()
        line_texts = [" ".join(tokens) for tokens in lines]
        return list(zip(line_texts, [self.id_to_label[p] for p in predictions]))
