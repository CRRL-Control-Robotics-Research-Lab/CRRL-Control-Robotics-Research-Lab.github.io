import os
import re
import unicodedata
import html
from collections import defaultdict
import bibtexparser

# --- Configuration ---
BIBTEX_FILE = 'files/references.bib'
TEMPLATE_FILE = 'publications_template.html'
OUTPUT_FILE = 'publications.html'
PLACEHOLDER = 'PLACEHOLDER' # Using the standard placeholder



# ------------------ Helpers ------------------
_ACCENT_COMBINING = {
    '"': '\u0308',  # diaeresis
    "'": '\u0301',  # acute
    '`': '\u0300',   # grave
    '^': '\u0302',   # circumflex
    '~': '\u0303',   # tilde
    'c': '\u0327',   # cedilla
    'k': '\u0328',   # ogonek
    'H': '\u030B',   # double acute
    'r': '\u030A',   # ring above
    '=': '\u0304',   # macron
    '.': '\u0307',   # dot above
    'u': '\u0306',   # breve
    'v': '\u030C',   # caron
    'd': '\u0323',   # dot below
    # 'b' tie/bar below is rare; skip or map to macron below
    'b': '\u0331',   # macron below (approximation)
}

_SPECIAL_MACROS = {
    r'\ss': 'ß', r'\SS': 'ẞ',
    r'\ae': 'æ', r'\AE': 'Æ',
    r'\oe': 'œ', r'\OE': 'Œ',
    r'\aa': 'å', r'\AA': 'Å',
    r'\o': 'ø',  r'\O': 'Ø',
    r'\l': 'ł',  r'\L': 'Ł',
}

_DASH_QUOTES = [
    (re.compile(r"---"), '—'),  # em dash
    (re.compile(r"--"), '–'),   # en dash
    (re.compile(r"``"), '“'),
    (re.compile(r"''"), '”'),
]

def latex_to_unicode(text: str) -> str:
    r"""Convert a subset of LaTeX accent commands to Unicode and strip braces.

    This handles patterns like \"{O}, \"O, \c{c}, etc., plus common macros like \ss.
    Remaining braces used for capitalization are removed. The result is NFC-normalized.
    """
    if not text:
        return text

    s = text

    # Replace special named macros first
    for macro, uni in _SPECIAL_MACROS.items():
        s = s.replace(macro, uni)

    # Replace accent commands with braced argument, e.g., \"{o}
    def _accent_braced(m):
        accent = m.group(1)
        base = m.group(2)
        combining = _ACCENT_COMBINING.get(accent)
        return base + (combining or '')

    s = re.sub(r"\\([\"'`\^~ckHr=\.uvdb])\{([A-Za-z])\}", _accent_braced, s)

    # Replace accent commands without braces, e.g., \"o
    s = re.sub(r"\\([\"'`\^~ckHr=\.uvdb])([A-Za-z])", _accent_braced, s)

    # Remove remaining curly braces used for grouping/capitalization
    s = s.replace('{', '').replace('}', '')

    # Replace common TeX quotes/dashes
    for pat, repl in _DASH_QUOTES:
        s = pat.sub(repl, s)

    # Normalize to NFC to combine into precomposed characters where possible
    s = unicodedata.normalize('NFC', s)
    return s

# Format authors from a raw BibTeX author string into a comma-separated list.
def format_authors(authors_raw: str) -> str:
    if not authors_raw:
        return 'No author specified'
    # Split on 'and' with arbitrary surrounding whitespace/newlines, ignore case
    parts = re.split(r"\s+and\s+", authors_raw.strip(), flags=re.IGNORECASE)
    norm_parts = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        # Convert LaTeX accents and collapse internal whitespace
        p = latex_to_unicode(p)
        p = re.sub(r"\s+", " ", p).strip()
        # Reorder 'Last, First' to 'First Last' when a single comma is present
        if "," in p:
            left, right = p.split(",", 1)
            left = left.strip()
            right = right.strip()
            if left and right:
                p = f"{right} {left}"
        norm_parts.append(p)
    # HTML-escape each name and join
    return ", ".join(html.escape(n) for n in norm_parts) if norm_parts else 'No author specified'

# ------------------ Main Processing ------------------
def main():
    """Reads the bibtex file, processes it, and updates the HTML output file."""
    
    try:
        with open(BIBTEX_FILE, 'r', encoding='utf-8') as bibfile:
            bib_database = bibtexparser.load(bibfile)
        
        # Group papers by year and sort years: numeric years descending, then others (e.g., 'Undated')
        grouped_by_year = defaultdict(list)
        for entry in bib_database.entries:
            grouped_by_year[entry.get('year', 'Undated')].append(entry)

        def _year_sort_key(y):
            try:
                return (0, -int(y))  # numeric years first, descending
            except Exception:
                return (1, str(y))   # non-numeric (e.g., 'Undated') after

        sorted_years = sorted(grouped_by_year.keys(), key=_year_sort_key)

        html_lines = []
        # Descending numbering across all publications
        total_pubs = sum(len(v) for v in grouped_by_year.values())
        current_number = total_pubs
        for year in sorted_years:
            html_lines.append(f'<h3 class="year-header">{year}</h3>')
            # Use reversed ordered list so numbers count down
            html_lines.append(f'<ol class="publication-list" reversed start="{current_number}">')
            
            papers_in_year = sorted(grouped_by_year[year], key=lambda x: x.get('author', ''))
            
            for entry in papers_in_year:
                # Convert LaTeX accents and escape for safe HTML output
                authors_raw = entry.get('author', 'No author specified')
                title_raw = entry.get('title', 'No title specified')
                authors = format_authors(authors_raw)
                title = html.escape(latex_to_unicode(title_raw))
                entry_year = entry.get('year', '')

                # --- Get URL for link ---
                link_url = entry.get('url') or None
                doi = entry.get('doi')
                if doi:
                    # If doi present but no URL, build a proper DOI URL
                    if not doi.lower().startswith('http'):
                        link_url = f'https://doi.org/{doi}'
                    else:
                        link_url = doi


                # if not link_url and doi:
                #     # If doi present but no URL, build a proper DOI URL
                #     if not doi.lower().startswith('http'):
                #         link_url = f'https://doi.org/{doi}'
                #     else:
                #         link_url = doi
                
                # UPDATED: The class is now on the <a> or <span> tag
                if link_url:
                    safe_href = html.escape(link_url, quote=True)
                    title_html = f'<a class="pub-title" href="{safe_href}" target="_blank" rel="noopener noreferrer">{title}</a>'
                else:
                    title_html = f'<span class="pub-title">{title}</span>'

                # --- Get and clean the venue name ---
                venue_raw = entry.get('journal') or entry.get('booktitle') or ''
                venue = latex_to_unicode(venue_raw)
                if not venue and entry.get('archivePrefix', '').lower() == 'arxiv':
                    venue = f"arXiv:{entry.get('eprint')}"
                if venue and entry_year:
                    venue = venue.replace(entry_year, '').strip(' ,.')
                venue = html.escape(venue)

                # --- Assemble the HTML ---
                html_lines.append(f'<li>{title_html}<div class="pub-authors">{authors}</div><div class="pub-venue">{venue}</div></li>')
            
            html_lines.append('</ol>')
            current_number -= len(papers_in_year)

        # ... (File writing logic is the same)
        generated_content = "\n".join(html_lines)
        with open(TEMPLATE_FILE, 'r', encoding='utf-8') as f:
            template_html = f.read()
        output_html = template_html.replace(PLACEHOLDER, generated_content)
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write(output_html)
        print(f"✅ Success! '{OUTPUT_FILE}' has been updated.")

    except Exception as e:
        print(f"❌ An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
