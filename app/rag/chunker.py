import re
from typing import List, Dict


class DocumentChunker:
    def __init__(self, max_chunk_size: int = 500):
        self.max_chunk_size = max_chunk_size

    def chunk_documents(self, documents: List[Dict]) -> List[Dict]:
        """
        Convert documents into chunks
        """
        chunks = []

        for doc in documents:
            doc_chunks = self._chunk_single_document(doc)
            chunks.extend(doc_chunks)

        return chunks

    def _chunk_single_document(self, doc: Dict) -> List[Dict]:
        content = doc["content"]
        metadata = doc["metadata"]

        sections = self._split_by_headers(content)

        chunks = []

        for idx, section in enumerate(sections):
            section_title, section_body = section

            sub_chunks = self._split_large_text(section_body)

            for sub_idx, text in enumerate(sub_chunks):
                chunk = {
                    "content": text.strip(),
                    "metadata": {
                        **metadata,
                        "section": section_title,
                        "chunk_id": f"{metadata.get('source')}_{idx}_{sub_idx}",
                    },
                }
                chunks.append(chunk)

        return chunks

    def _split_by_headers(self, text: str):
        """
        Split markdown text into sections using ## headers
        """
        pattern = r"## (.+)"
        parts = re.split(pattern, text)

        sections = []

        if len(parts) <= 1:
            return [("general", text)]

        for i in range(1, len(parts), 2):
            header = parts[i].strip()
            body = parts[i + 1].strip() if i + 1 < len(parts) else ""
            sections.append((header, body))

        return sections

    def _split_large_text(self, text: str) -> List[str]:
        """
        Split large text into smaller chunks
        """
        if len(text) <= self.max_chunk_size:
            return [text]

        paragraphs = text.split("\n\n")

        chunks = []
        current = ""

        for para in paragraphs:
            if len(current) + len(para) < self.max_chunk_size:
                current += para + "\n\n"
            else:
                chunks.append(current.strip())
                current = para + "\n\n"

        if current:
            chunks.append(current.strip())

        return chunks
