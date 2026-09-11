import pytest
from backend.ingestion.chunker import Chunker

def test_chunker_code_block_preservation():
    """
    Test that the chunker does not blindly split inside a Python code block 
    even if the chunk size boundary falls exactly inside it.
    """
    chunker = Chunker(chunk_size=100, chunk_overlap=0)
    
    # A text with a python code block that straddles the 100 character boundary.
    # Total length > 100
    markdown_text = (
        "Here is a brief introduction to the code block below.\n\n"
        "```python\n"
        "def hello_world():\n"
        "    print('Hello world!')\n"
        "    # This is a very long comment to push the length over 100 chars\n"
        "    return True\n"
        "```\n\n"
        "End of the document."
    )
    
    chunks = chunker.split_text(markdown_text)
    
    # We assert that NO chunk contains ONLY the beginning or ONLY the end of the code block.
    # If the chunker splits purely on "\n" or " ", we will have orphaned backticks.
    orphaned_backticks = [c.text for c in chunks if c.text.count("```") == 1]
    
    # NOTE: With standard recursive splitters, this will FAIL and return orphaned backticks!
    assert len(orphaned_backticks) == 0, f"Chunker bisected a code block! Orphaned chunks: {orphaned_backticks}"

def test_chunker_json_preservation():
    """
    Test that the chunker does not bisect JSON objects.
    """
    chunker = Chunker(chunk_size=50, chunk_overlap=0)
    
    json_text = (
        "Here is the JSON payload:\n\n"
        "```json\n"
        "{\n"
        '  "key1": "value1",\n'
        '  "key2": "value2"\n'
        "}\n"
        "```\n\n"
        "Done."
    )
    
    chunks = chunker.split_text(json_text)
    orphaned_backticks = [c.text for c in chunks if c.text.count("```") == 1]
    
    assert len(orphaned_backticks) == 0, f"Chunker bisected JSON payload! Orphaned chunks: {orphaned_backticks}"
