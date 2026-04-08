import unidecode
from datasets import load_dataset

ds = load_dataset("AKCIT/MedPT")

seen = set()
def remove_duplicates(example):
    key = (example['question'],example['answer'])

    if key in seen:
        return False

    seen.add(key)
    return True

ds = ds.filter(remove_duplicates)

def filter_health_woman(example):

    specialty = str(example['medical_specialty']).lower()
    specialty = unidecode.unidecode(specialty)

    if "ginec" in specialty or "obstet" in specialty:
        return True

    text = str(example['question']).lower()
    if "menopausa" in text or "gravidez" in text:
        return True

    return False

dataset_filter = ds.filter(filter_health_woman)

def format_io(example):
    return {
        "input": example['question'],
        "output": example["answer"]
    }

dataset_io = dataset_filter["train"].map(format_io, remove_columns=dataset_filter["train"].column_names)
dataset_io.to_json("dataset_health_fem.jsonl", force_ascii=False)

