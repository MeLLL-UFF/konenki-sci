import os
import unidecode
from datasets import load_dataset

hf_token = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_TOKEN") or os.getenv("HF_HUB_TOKEN")


def load_base_dataset():
    if hf_token:
        return load_dataset("AKCIT/MedPT", use_auth_token=hf_token)
    return load_dataset("AKCIT/MedPT")


def remove_duplicates(example):
    key = (example['question'], example['answer'])

    if key in remove_duplicates.seen:
        return False
    
    remove_duplicates.seen.add(key)
    return True

remove_duplicates.seen = set()


def filter_health_woman(example):

    specialty = str(example['medical_specialty']).lower()
    specialty = unidecode.unidecode(specialty)

    if "ginec" in specialty or "obstet" in specialty:
        return True

    text = str(example['question']).lower()
    if "menopausa" in text or "gravidez" in text:
        return True

    return False


def format_io(example):
    return {
        "input": example['question'],
        "output": example["answer"],
    }


def load_health_female_dataset():
    ds = load_base_dataset()
    remove_duplicates.seen.clear()
    ds = ds.filter(remove_duplicates)
    ds = ds.filter(filter_health_woman)
    return ds["train"].map(format_io, remove_columns=ds["train"].column_names).to_list()


if __name__ == "__main__":
    dataset_io = load_health_female_dataset()
    dataset_io.to_json("dataset_health_fem.jsonl", force_ascii=False)

