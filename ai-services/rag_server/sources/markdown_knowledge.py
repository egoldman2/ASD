"""Bounded curated Markdown sources; no ticket data or client-chosen file paths."""

from hashlib import sha256
from pathlib import Path
import re
import textwrap

from .base import KnowledgeDocument, KnowledgeSource, SourceDataError, SourceUnavailableError


MAX_FILE_BYTES = 64 * 1024
MAX_FILES = 40
MAX_CHUNKS = 200
CHUNK_SIZE = 1000


class MarkdownKnowledgeSource(KnowledgeSource):
    def __init__(self, *, scope, directory, source_name):
        self._scope = scope
        self.directory = Path(directory)
        self._source_name = source_name

    @property
    def scope(self):
        return self._scope

    @property
    def source_name(self):
        return self._source_name

    def load_documents(self):
        if self.directory.is_symlink():
            raise SourceDataError('Curated knowledge directories must not be symlinks.')
        if not self.directory.is_dir():
            raise SourceUnavailableError('The curated knowledge directory is unavailable.')
        paths = sorted(self.directory.glob('*.md'))
        if len(paths) > MAX_FILES:
            raise SourceDataError('The curated knowledge source contains too many files.')
        documents = []
        for path in paths:
            if path.is_symlink() or not path.is_file():
                raise SourceDataError('Curated knowledge must contain regular Markdown files.')
            try:
                with path.open('rb') as stream:
                    raw = stream.read(MAX_FILE_BYTES + 1)
                if len(raw) > MAX_FILE_BYTES:
                    raise SourceDataError('A curated knowledge file exceeds its size limit.')
                text = raw.decode('utf-8').strip()
            except (OSError, UnicodeError):
                raise SourceDataError('A curated knowledge file could not be read as UTF-8.') from None
            if not text:
                raise SourceDataError('Curated knowledge files must not be empty.')
            revision = sha256(raw).hexdigest()
            title, section = path.stem.replace('_', ' ').title(), ''
            chunk_index = 0
            for block in re.split(r'\n\s*\n', text):
                if re.fullmatch(r'#{1,6}\s+[^\n]+', block):
                    heading = block.lstrip('#').strip()
                    if len(heading) > 160:
                        raise SourceDataError('Curated knowledge headings exceed their size limit.')
                    if block.startswith('# '):
                        title = heading
                    else:
                        section = heading
                    continue
                for chunk in textwrap.wrap(block, width=CHUNK_SIZE, replace_whitespace=False, break_on_hyphens=False):
                    label = title + (': ' + section if section else '')
                    documents.append(KnowledgeDocument(
                        document_id=f'{self.scope}:{path.name}:{chunk_index}', scope=self.scope,
                        source_id=f'{self.scope}/{path.name}', citation_label=label,
                        text=f'{label}\n\n{chunk}', metadata={
                            'source_file': path.name, 'section': section, 'chunk_index': chunk_index,
                            'revision': revision, 'curated': True,
                        },
                    ))
                    chunk_index += 1
                    if len(documents) > MAX_CHUNKS:
                        raise SourceDataError('The curated knowledge source contains too many chunks.')
        return documents
