"""Rebuild the document-only knowledge index: python -m backend.rag.ingest."""
import argparse
from pathlib import Path

from backend import config
from backend.rag import vector_store


DIRECTORIES = ('mitre', 'policies', 'historical_incidents')


def parse_document(text: str) -> tuple[dict, list[dict]]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != '---':
        raise ValueError('Missing opening front matter delimiter')
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == '---'), None)
    if end is None:
        raise ValueError('Missing closing front matter delimiter')
    metadata = {}
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        key, separator, value = line.partition(':')
        if not separator:
            raise ValueError('Invalid metadata field')
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        metadata[key.strip()] = value
    for key in ('doc_id', 'title', 'source_type'):
        if not metadata.get(key):
            raise ValueError(f'Missing {key}')
    chunks = []
    section = None
    body = []

    def flush():
        if section is not None:
            chunks.append({'doc_id': metadata['doc_id'], 'title': metadata['title'],
                           'source_type': metadata['source_type'], 'section': section,
                           **({'url': metadata['url']} if metadata.get('url') else {}),
                           'text': '\n'.join(body).strip()})

    for line in lines[end + 1:]:
        if line.startswith('## '):
            flush()
            section = line[3:].strip()
            body = []
        elif section is not None:
            body.append(line)
    flush()
    # Keep original headings for citations, but disambiguate storage IDs. Reserve
    # all literal section names first, including headings like "Summary [2]".
    reserved = {c['section'] for c in chunks}
    used = set()
    for chunk in chunks:
        section = chunk['section']
        suffix = section
        if section in used:
            number = 2
            while f'{section} [{number}]' in reserved | used:
                number += 1
            suffix = f'{section} [{number}]'
        used.add(suffix)
        if suffix != section:
            chunk['chunk_id'] = f"{chunk['doc_id']}#{suffix}"
    return metadata, chunks


def read_chunks(root: Path, include_test_fixtures: bool = False):
    chunks, errors, documents = [], [], 0
    seen = set()
    folders = DIRECTORIES + (('test_fixtures',) if include_test_fixtures else ())
    for folder in folders:
        for path in sorted((root / folder).rglob('*.md')):
            if not include_test_fixtures and 'test_fixtures' in path.relative_to(root).parts:
                continue
            try:
                _, sections = parse_document(path.read_text(encoding='utf-8'))
                ids = [chunk_id(c) for c in sections]
                if not sections or len(set(ids)) != len(ids) or seen.intersection(ids):
                    raise ValueError('Empty document or duplicate chunk IDs')
                seen.update(ids)
                chunks.extend(sections)
                documents += 1
            except (ValueError, OSError) as exc:
                errors.append(f'{path.name}: {exc}')
    return documents, chunks, errors


def chunk_id(chunk):
    return chunk.get('chunk_id', f"{chunk['doc_id']}#{chunk['section']}")


def ingest(include_test_fixtures: bool = False):
    documents, chunks, errors = read_chunks(config.ROOT / 'data/knowledge', include_test_fixtures)
    model = vector_store.get_model(config.EMBEDDING_MODEL)
    embeddings = model.encode([c['text'] for c in chunks]).tolist() if chunks else []
    collection = vector_store.rebuild_collection()
    if chunks:
        collection.add(ids=[chunk_id(c) for c in chunks],
                       documents=[c['text'] for c in chunks], embeddings=embeddings,
                       metadatas=[{k: v for k, v in c.items() if k not in ('text', 'chunk_id')} for c in chunks])
    print(f'Documents processed: {documents}; chunks stored: {collection.count()}; skipped/errors: {len(errors)}')
    if not include_test_fixtures:
        print('Excluded test_fixtures/ (use --include-test-fixtures to include).')
    for error in errors:
        print(error)
    return documents, len(chunks), errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--include-test-fixtures', action='store_true')
    args = parser.parse_args()
    ingest(args.include_test_fixtures)


if __name__ == '__main__':
    main()
