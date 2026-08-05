import pandas as pd

from config import OUTPUT_DIR


def yes_no_score(value):
    value = str(value).strip().lower()
    if value in {"yes", "y", "1", "true"}:
        return 1
    if value in {"no", "n", "0", "false"}:
        return 0
    return None


def main() -> int:
    review_path = OUTPUT_DIR / "review_template.csv"
    if not review_path.exists():
        print("Run the MVP first. The review template is not available yet.")
        return 1

    review = pd.read_csv(review_path)
    summary_rows = []

    classification_column = (
        "classification_result"
        if "classification_result" in review.columns
        else "classification_correct_yes_no"
    )
    caption_column = (
        "best_caption_blip_florence"
        if "best_caption_blip_florence" in review.columns
        else "best_caption_blip_florence_tie"
    )

    classification_scores = review[classification_column].map(yes_no_score)
    scored_classifications = classification_scores.dropna()
    if not scored_classifications.empty:
        summary_rows.append(
            {
                "measure": "clip_classification_accuracy",
                "value": round(scored_classifications.mean(), 3),
                "scored_items": len(scored_classifications),
            }
        )

    caption_choices = (
        review[caption_column]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
    )
    for choice in ["blip", "florence", "tie"]:
        count = int((caption_choices == choice).sum())
        if count:
            summary_rows.append(
                {
                    "measure": f"caption_preference_{choice}",
                    "value": count,
                    "scored_items": int(caption_choices.isin(["blip", "florence", "tie"]).sum()),
                }
            )

    if not summary_rows:
        print("Fill in the review columns before running this script.")
        return 1

    pd.DataFrame(summary_rows).to_csv(
        OUTPUT_DIR / "review_summary.csv",
        index=False,
    )
    print("Review summary saved in the outputs folder.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
