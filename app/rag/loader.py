import os
import yaml
from typing import List, Dict


class DocumentLoader:
    def __init__(self, base_path: str = "data/knowledge_base"):
        self.base_path = base_path

    def load_documents(self) -> List[Dict]:
        """
        Load all markdown files and parse into structured documents
        """
        documents = []

        for root, _, files in os.walk(self.base_path):
            for file in files:
                if file.endswith(".md"):
                    full_path = os.path.join(root, file)

                    doc = self._load_single_file(full_path)
                    if doc:
                        documents.append(doc)

        return documents

    def _load_single_file(self, file_path: str) -> Dict:
        """
        Load and parse a single markdown file
        """
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        if content.startswith("---"):
            parts = content.split("---", 2)

            if len(parts) >= 3:
                metadata_raw = parts[1]
                body = parts[2]

                metadata = yaml.safe_load(metadata_raw)
            else:
                metadata = {}
                body = content
        else:
            metadata = {}
            body = content

        metadata["source"] = os.path.basename(file_path)

        return {"content": body.strip(), "metadata": metadata}
