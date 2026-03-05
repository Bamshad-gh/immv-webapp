# cases/crawler/pdf_parser.py
# ─────────────────────────────────────────────────────────────
# Extract form field metadata from fillable (AcroForm) PDF files.
#
# Government fillable PDFs (e.g. IMM5710E.pdf) contain an AcroForm
# structure — a list of named interactive fields (text inputs, checkboxes,
# radio buttons, dropdowns) embedded in the PDF's cross-reference table.
#
# What we extract per field:
#   - field_id    : the internal field name (e.g. 'Section2_FamilyName')
#   - label       : human-readable tooltip or partial-name (e.g. 'Family Name / Nom de famille')
#   - field_type  : 'text', 'checkbox', 'radio', 'dropdown', 'signature'
#   - is_required : True if the PDF marks this field as required
#   - options     : list of choices for dropdown/radio fields
#
# ── Library Options (choose one) ─────────────────────────────
#
# OPTION A — pypdf (pure Python, no C dependencies, easiest to install)
#   pip install pypdf
#   Fields: pypdf.PdfReader → reader.get_fields()
#   PRO: no native dependencies, works on all platforms
#   CON: limited; some locked/encrypted PDFs may not parse correctly
#
# OPTION B — PyMuPDF / fitz (fastest, best coverage, C extension)
#   pip install pymupdf
#   Fields: fitz.open() → page.widgets()
#   PRO: handles protected PDFs, extremely fast, extracts text blocks too
#   CON: requires compiled C extension; larger install size
#
# OPTION C — pdfminer.six (best text extraction, AcroForm via pdfrw)
#   pip install pdfminer.six pdfrw
#   Use pdfrw for fields, pdfminer for page text
#
# CURRENT IMPLEMENTATION: tries pypdf first, falls back to PyMuPDF,
# falls back to a stub that returns empty (keeps the pipeline running even
# if neither library is installed).
#
# SWITCH LIBRARY: change PREFERRED_LIBRARY constant below.
# ─────────────────────────────────────────────────────────────

# CUSTOMIZE: set to 'pypdf', 'pymupdf', or 'auto' (tries both)
PREFERRED_LIBRARY = 'auto'


def extract_pdf_fields(pdf_bytes: bytes) -> list[dict]:
    """
    Extract all form fields from a fillable PDF.

    Args:
        pdf_bytes: raw PDF content as bytes (from scraper.fetch_pdf_bytes)

    Returns:
        List of field dicts:
        [
          {
            'field_id':   'Section2_FamilyName',   # internal PDF field name
            'label':      'Family Name',            # tooltip or cleaned name
            'field_type': 'text',                   # text|checkbox|radio|dropdown|signature
            'is_required': False,                   # PDF-level required flag
            'options':    [],                       # choices for dropdown/radio; empty for others
          },
          ...
        ]

    Returns empty list if:
      - No AcroForm found (PDF is not a fillable form — just a static PDF)
      - PDF is encrypted and cannot be read
      - Neither pypdf nor PyMuPDF is installed

    EXPAND: add 'page_number' to each field so the UI can show which page
            the field appears on (useful for very long forms like IMM5257).
    """
    if PREFERRED_LIBRARY == 'pypdf':
        return _extract_with_pypdf(pdf_bytes)
    elif PREFERRED_LIBRARY == 'pymupdf':
        return _extract_with_pymupdf(pdf_bytes)
    else:
        # 'auto' — try pypdf, fall back to pymupdf, fall back to stub
        fields = _extract_with_pypdf(pdf_bytes)
        if fields is not None:
            return fields
        fields = _extract_with_pymupdf(pdf_bytes)
        if fields is not None:
            return fields
        return _extract_stub(pdf_bytes)


# ── OPTION A: pypdf implementation ───────────────────────────
def _extract_with_pypdf(pdf_bytes: bytes) -> list[dict] | None:
    """
    Extract fields using the pypdf library.
    Returns None if pypdf is not installed so the caller can fall back.

    Install: pip install pypdf
    Docs: https://pypdf.readthedocs.io/en/latest/user/extract-form.html

    EXPAND: to handle password-protected PDFs (some IRCC forms):
      reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
      if reader.is_encrypted:
          reader.decrypt('')   # try blank password first
    """
    try:
        import pypdf            # noqa: F401 — check availability
        import io

        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        raw_fields = reader.get_fields()
        if not raw_fields:
            return []           # not a fillable form

        fields = []
        for field_name, field_obj in raw_fields.items():
            field_type = _map_pypdf_type(field_obj.get('/FT', ''))
            label      = _clean_field_name(field_obj.get('/TU', '') or field_name)
            options    = _extract_pypdf_options(field_obj)
            is_req     = bool(field_obj.get('/Ff', 0) & 0x2)  # bit 1 = Required flag in AcroForm spec

            fields.append({
                'field_id':   field_name,
                'label':      label,
                'field_type': field_type,
                'is_required': is_req,
                'options':    options,
            })

        return fields

    except ImportError:
        return None     # pypdf not installed — caller will try next option
    except Exception:
        return []       # PDF unreadable — return empty, don't crash


def _map_pypdf_type(ft_value: str) -> str:
    """Map PDF AcroForm /FT value to our internal type name."""
    # AcroForm field type codes (PDF spec section 12.7.3):
    #   /Tx = Text field, /Btn = Button (checkbox or radio), /Ch = Choice (dropdown/listbox), /Sig = Signature
    mapping = {'/Tx': 'text', '/Btn': 'checkbox', '/Ch': 'dropdown', '/Sig': 'signature'}
    return mapping.get(ft_value, 'text')


def _extract_pypdf_options(field_obj) -> list[str]:
    """Extract choice options from a dropdown/radio field."""
    opt = field_obj.get('/Opt', [])
    result = []
    for item in opt:
        if isinstance(item, list) and item:
            result.append(str(item[0]))   # option display value
        elif item:
            result.append(str(item))
    return result


# ── OPTION B: PyMuPDF implementation ─────────────────────────
def _extract_with_pymupdf(pdf_bytes: bytes) -> list[dict] | None:
    """
    Extract fields using PyMuPDF (fitz).
    Returns None if PyMuPDF is not installed.

    Install: pip install pymupdf
    Docs: https://pymupdf.readthedocs.io/en/latest/widget.html

    WHY PyMuPDF over pypdf:
      PyMuPDF can handle more PDF variants and is ~10x faster.
      It also extracts widget (field) data with higher fidelity.
      Use it if pypdf fails on a specific government PDF.

    EXPAND: also extract page text with doc.get_text('text') for
            better NLP matching context beyond just field names.
    """
    try:
        import fitz             # fitz = PyMuPDF; noqa: F401
        import io

        doc = fitz.open(stream=pdf_bytes, filetype='pdf')
        fields = []
        seen_names = set()

        for page in doc:
            for widget in page.widgets():
                name = widget.field_name or ''
                if name in seen_names:
                    continue    # deduplicate fields that span pages
                seen_names.add(name)

                field_type = _map_fitz_type(widget.field_type_string)
                label      = _clean_field_name(widget.field_label or name)
                options    = list(widget.choice_values or [])
                is_req     = bool(widget.field_flags & 0x2)

                fields.append({
                    'field_id':    name,
                    'label':       label,
                    'field_type':  field_type,
                    'is_required': is_req,
                    'options':     options,
                })

        doc.close()
        return fields

    except ImportError:
        return None
    except Exception:
        return []


def _map_fitz_type(type_string: str) -> str:
    """Map PyMuPDF field type string to our internal type name."""
    type_string = (type_string or '').lower()
    if 'text'       in type_string: return 'text'
    if 'check'      in type_string: return 'checkbox'
    if 'radio'      in type_string: return 'radio'
    if 'list'       in type_string: return 'dropdown'
    if 'combo'      in type_string: return 'dropdown'
    if 'signature'  in type_string: return 'signature'
    return 'text'


# ── FALLBACK STUB ─────────────────────────────────────────────
def _extract_stub(pdf_bytes: bytes) -> list[dict]:
    """
    Fallback when neither pypdf nor PyMuPDF is installed.
    Returns empty list — the pipeline will log a warning.

    TO INSTALL A REAL PARSER:
      pip install pypdf         (lightweight, pure Python)
      pip install pymupdf       (powerful, requires C extension)

    After installing, set PREFERRED_LIBRARY = 'pypdf' or 'pymupdf'
    at the top of this file and restart the Django server.
    """
    return []


# ── SHARED HELPERS ────────────────────────────────────────────
def _clean_field_name(name: str) -> str:
    """
    Convert a raw PDF field name or tooltip into a human-readable label.

    Examples:
      'Section2_FamilyName'   → 'Family Name'
      'Part3_DOB'             → 'DOB'
      'Family Name / Nom de famille' → 'Family Name / Nom de famille'  (already readable)

    EXPAND: add bilingual splitting — split on '/' or 'Nom de' to get English-only label.
    EXPAND: add acronym expansion: 'DOB' → 'Date of Birth' using a small lookup dict.
    """
    if not name:
        return ''
    # Remove common prefixes like "Section2_", "Part3_", "pg1[0]."
    import re
    name = re.sub(r'^[A-Za-z]+\d+[_\.]', '', name)  # remove 'Section2_', 'Part3.'
    name = re.sub(r'^\[\d+\]\.', '', name)           # remove '[0].'
    # Split camelCase → words: 'FamilyName' → 'Family Name'
    name = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)
    # Replace underscores and hyphens with spaces
    name = name.replace('_', ' ').replace('-', ' ')
    # Collapse multiple spaces
    name = re.sub(r'\s+', ' ', name).strip()
    return name
