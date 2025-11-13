import pandas as pd
from datasets import Dataset, DatasetDict
from pathlib import Path
from typing import Optional
import json


#############################################
####      Our (=manually crafted) dataset
#############################################
def load_our_dataset(
    master_labels_path: str = "data/data_generation/master_label.csv",
    labels_dir: str = "data/txt/",
    encoding: str = "utf-8"
) -> DatasetDict:
    """
    Load dataset from master_labels.txt and corresponding label files.

    Args:
        master_labels_path: Path to the master labels CSV file
        labels_dir: Directory containing label files
        encoding: Encoding of the label files (default: utf-16 for the data files)

    Returns:
        HuggingFace DatasetDict with train split containing metadata and label content
    """
    # Read the master labels CSV
    df = pd.read_csv(master_labels_path, sep=",", encoding=encoding)

    # Clean column names (remove any extra spaces)
    df.columns = df.columns.str.strip()

    # Rename company_address to address
    df = df.rename(columns={'company_address': 'address'})

    labels_path = Path(labels_dir)

    # Add label content column
    label_contents = []
    for file_name in df['file_name']:
        prefix = "paddle_"
        label_file_path = labels_path / f"{prefix}{file_name}.txt"
        try:
            with open(label_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            # Try with different encodings if utf-8 fails
            try:
                with open(label_file_path, 'r', encoding='latin-1') as f:
                    content = f.read()
            except Exception as e:
                print(f"Warning: Could not read {label_file_path}: {e}")
                content = ""
        except Exception as e:
            print(f"Warning: Could not read {label_file_path}: {e}")
            content = ""

        label_contents.append(content)

    df['text'] = label_contents

    # Convert to HuggingFace Dataset
    dataset = Dataset.from_pandas(df)

    # Wrap in DatasetDict with train split
    dataset_dict = DatasetDict({
        'train': dataset
    })

    return dataset_dict


def main():
    """Example usage"""
    dataset = load_our_dataset()

    print(f"Dataset loaded with {len(dataset)} examples")
    print(dataset)

    print(f"\nColumns: {dataset['train'].column_names}")
    print(f"\nFirst example:")
    print(f">{dataset['train'][0]}<")


if __name__ == "__main__":
    main()
