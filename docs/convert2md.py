#!/usr/bin/env python3
"""
convert2md.py - Convert poorly formatted documents to well-formed Markdown

This script uses Azure OpenAI to intelligently convert text documents that lack
proper markdown formatting into well-structured markdown documents.

Usage:
    python convert2md.py <input_file> [output_file]
    python convert2md.py ../settofalse.md                    # Overwrites input
    python convert2md.py ../settofalse.md ./settofalse.md    # Outputs to docs/

Environment Variables Required:
    OPENAI_ENDPOINT - Azure OpenAI endpoint URL
    AZURE_OPENAI_API_KEY - Azure OpenAI API key
    OPENAI_DEPLOYMENT_PERSONA_CORE_CHAT - Deployment name for chat model

Features:
    - Converts numbered sections to proper markdown headers (#, ##, ###)
    - Formats code snippets with appropriate language tags
    - Creates proper bullet lists and nested lists
    - Adds code blocks for commands, URLs, and technical content
    - Preserves document structure and meaning
    - Adds table of contents for longer documents
"""

import os
import sys
import re
import argparse
from pathlib import Path
from typing import Optional

# Try to import Azure OpenAI - provide helpful error if not available
try:
    from openai import AzureOpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


def get_openai_client() -> Optional[AzureOpenAI]:
    """Create Azure OpenAI client from environment variables."""
    endpoint = os.environ.get("OPENAI_ENDPOINT")
    api_key = os.environ.get("AZURE_OPENAI_API_KEY")

    if not endpoint or not api_key:
        return None

    return AzureOpenAI(
        azure_endpoint=endpoint,
        api_key=api_key,
        api_version="2024-02-15-preview"
    )


def convert_with_ai(content: str, client: AzureOpenAI, deployment: str) -> str:
    """Use AI to convert content to well-formed markdown."""

    system_prompt = """You are a markdown formatting expert. Convert the provided text into
well-formed, properly structured Markdown. Follow these rules:

1. HEADERS:
   - Main title becomes # (H1)
   - Major sections (1, 2, 3...) become ## (H2)
   - Subsections (1.1, 1.2, 2.1...) become ### (H3)
   - Further nesting uses #### (H4)

2. CODE AND COMMANDS:
   - Wrap shell commands in ```bash code blocks
   - Wrap URLs in backticks for inline or code blocks if standalone
   - Wrap variable names, file paths, and technical terms in backticks
   - Use appropriate language tags (bash, terraform, powershell, etc.)

3. LISTS:
   - Convert implicit lists to proper bullet points (-)
   - Use numbered lists (1., 2., 3.) for sequential steps
   - Properly indent nested items
   - Use checkbox syntax (- [ ]) for task items when appropriate

4. STRUCTURE:
   - Add horizontal rules (---) between major sections
   - Use blockquotes (>) for important notes or warnings
   - Create tables when data is tabular
   - Add emphasis (**bold**, *italic*) for important terms

5. PRESERVE:
   - Keep all original content and meaning
   - Maintain the document's logical flow
   - Don't add new information, only format existing content

Output ONLY the converted markdown, no explanations or commentary."""

    user_prompt = f"""Convert this document to well-formed Markdown:

---
{content}
---

Output the properly formatted Markdown:"""

    response = client.chat.completions.create(
        model=deployment,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.1,
        max_tokens=8000
    )

    return response.choices[0].message.content.strip()


def convert_with_rules(content: str) -> str:
    """Convert content using rule-based approach (fallback when AI unavailable)."""

    lines = content.split('\n')
    result = []
    in_code_block = False

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Skip empty lines but preserve them
        if not stripped:
            result.append('')
            i += 1
            continue

        # Detect code blocks (lines that look like commands or code)
        if stripped.startswith(('curl ', 'nslookup ', 'npm ', 'pip ', 'terraform ',
                                'az ', 'git ', 'docker ', 'kubectl ')):
            result.append('```bash')
            result.append(stripped)
            result.append('```')
            i += 1
            continue

        # Convert section headers like "1) Title" or "1.1 Title"
        section_match = re.match(r'^(\d+)\)\s*(.+)$', stripped)
        if section_match:
            result.append(f'## {section_match.group(1)}. {section_match.group(2)}')
            result.append('')
            i += 1
            continue

        subsection_match = re.match(r'^(\d+\.\d+)\s+(.+)$', stripped)
        if subsection_match:
            result.append(f'### {subsection_match.group(1)} {subsection_match.group(2)}')
            result.append('')
            i += 1
            continue

        subsubsection_match = re.match(r'^(\d+\.\d+\.\d+)\s+(.+)$', stripped)
        if subsubsection_match:
            result.append(f'#### {subsubsection_match.group(1)} {subsubsection_match.group(2)}')
            result.append('')
            i += 1
            continue

        # Single word or short phrase at start might be a title
        if i == 0 and len(stripped.split()) <= 5 and not any(c in stripped for c in '.,:;'):
            result.append(f'# {stripped}')
            result.append('')
            i += 1
            continue

        # Lines ending with colon often introduce lists
        if stripped.endswith(':') and len(stripped) > 10:
            result.append(f'**{stripped}**')
            result.append('')
            i += 1
            continue

        # Detect bullet-like patterns
        bullet_match = re.match(r'^[-•]\s*(.+)$', stripped)
        if bullet_match:
            result.append(f'- {bullet_match.group(1)}')
            i += 1
            continue

        # Detect variable assignments
        if '=' in stripped and not ' ' in stripped.split('=')[0]:
            result.append(f'`{stripped}`')
            result.append('')
            i += 1
            continue

        # Wrap URLs in backticks
        url_pattern = r'(https?://[^\s]+)'
        if re.search(url_pattern, stripped):
            modified = re.sub(url_pattern, r'`\1`', stripped)
            result.append(modified)
            i += 1
            continue

        # Check for "Or:" or "Notes:" patterns (make them bold)
        label_match = re.match(r'^(Or|Notes|Plan|Best practice|Tip|Warning|Important):\s*(.*)$', stripped, re.IGNORECASE)
        if label_match:
            if label_match.group(2):
                result.append(f'**{label_match.group(1)}:** {label_match.group(2)}')
            else:
                result.append(f'**{label_match.group(1)}:**')
            i += 1
            continue

        # Default: keep the line as-is
        result.append(stripped)
        i += 1

    return '\n'.join(result)


def add_table_of_contents(content: str) -> str:
    """Add a table of contents based on headers."""

    lines = content.split('\n')
    headers = []

    for line in lines:
        if line.startswith('## '):
            title = line[3:].strip()
            anchor = re.sub(r'[^\w\s-]', '', title.lower()).replace(' ', '-')
            headers.append(f'- [{title}](#{anchor})')
        elif line.startswith('### '):
            title = line[4:].strip()
            anchor = re.sub(r'[^\w\s-]', '', title.lower()).replace(' ', '-')
            headers.append(f'  - [{title}](#{anchor})')

    if len(headers) < 3:
        return content

    # Find where to insert TOC (after first H1)
    toc_content = '\n## Table of Contents\n\n' + '\n'.join(headers) + '\n\n---\n'

    for i, line in enumerate(lines):
        if line.startswith('# ') and not line.startswith('## '):
            # Insert after H1 and any following blank lines
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            lines.insert(j, toc_content)
            break

    return '\n'.join(lines)


def detect_format_quality(content: str) -> float:
    """
    Estimate how well-formatted the document already is.
    Returns a score from 0.0 (poorly formatted) to 1.0 (well formatted).
    """

    lines = content.split('\n')
    total_lines = len([l for l in lines if l.strip()])

    if total_lines == 0:
        return 1.0

    indicators = 0

    # Check for markdown headers
    headers = len([l for l in lines if re.match(r'^#{1,6}\s+', l)])
    indicators += min(headers / max(total_lines * 0.1, 1), 1.0) * 0.25

    # Check for code blocks
    code_blocks = content.count('```')
    indicators += min(code_blocks / 4, 1.0) * 0.25

    # Check for bullet lists
    bullets = len([l for l in lines if re.match(r'^\s*[-*]\s+', l)])
    indicators += min(bullets / max(total_lines * 0.2, 1), 1.0) * 0.25

    # Check for inline code
    inline_code = len(re.findall(r'`[^`]+`', content))
    indicators += min(inline_code / 5, 1.0) * 0.25

    return indicators


def main():
    parser = argparse.ArgumentParser(
        description='Convert poorly formatted documents to well-formed Markdown',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python convert2md.py ../settofalse.md
    python convert2md.py input.txt output.md
    python convert2md.py --check-only document.md
    python convert2md.py --no-ai document.txt
        """
    )

    parser.add_argument('input_file', help='Input file to convert')
    parser.add_argument('output_file', nargs='?', help='Output file (default: overwrite input)')
    parser.add_argument('--check-only', action='store_true',
                        help='Only check format quality, do not convert')
    parser.add_argument('--no-ai', action='store_true',
                        help='Use rule-based conversion only (no AI)')
    parser.add_argument('--no-toc', action='store_true',
                        help='Do not add table of contents')
    parser.add_argument('--force', action='store_true',
                        help='Convert even if document appears well-formatted')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Verbose output')

    args = parser.parse_args()

    # Resolve paths
    input_path = Path(args.input_file).resolve()
    output_path = Path(args.output_file).resolve() if args.output_file else input_path

    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    # Read input
    content = input_path.read_text(encoding='utf-8')

    if args.verbose:
        print(f"Read {len(content)} characters from {input_path}")

    # Check format quality
    quality = detect_format_quality(content)

    if args.check_only:
        print(f"Format quality score: {quality:.2f}")
        print(f"  0.0 = poorly formatted, 1.0 = well formatted")
        if quality > 0.7:
            print("  Document appears to be reasonably well-formatted.")
        elif quality > 0.4:
            print("  Document has some formatting but could be improved.")
        else:
            print("  Document needs significant formatting improvements.")
        sys.exit(0)

    # Skip if already well-formatted (unless forced)
    if quality > 0.7 and not args.force:
        print(f"Document appears well-formatted (score: {quality:.2f}). Use --force to convert anyway.")
        sys.exit(0)

    # Choose conversion method
    use_ai = not args.no_ai and HAS_OPENAI

    if use_ai:
        client = get_openai_client()
        deployment = os.environ.get("OPENAI_DEPLOYMENT_PERSONA_CORE_CHAT", "gpt-4")

        if client:
            if args.verbose:
                print(f"Using AI conversion with deployment: {deployment}")

            try:
                converted = convert_with_ai(content, client, deployment)
            except Exception as e:
                print(f"AI conversion failed: {e}", file=sys.stderr)
                print("Falling back to rule-based conversion...", file=sys.stderr)
                converted = convert_with_rules(content)
        else:
            if args.verbose:
                print("OpenAI credentials not found, using rule-based conversion")
            converted = convert_with_rules(content)
    else:
        if args.verbose:
            print("Using rule-based conversion")
        converted = convert_with_rules(content)

    # Add table of contents if requested
    if not args.no_toc:
        converted = add_table_of_contents(converted)

    # Write output
    output_path.write_text(converted, encoding='utf-8')

    new_quality = detect_format_quality(converted)

    print(f"Converted: {input_path.name}")
    print(f"  Output: {output_path}")
    print(f"  Quality: {quality:.2f} -> {new_quality:.2f}")

    if args.verbose:
        print(f"  Lines: {len(content.splitlines())} -> {len(converted.splitlines())}")
        print(f"  Characters: {len(content)} -> {len(converted)}")


if __name__ == '__main__':
    main()
