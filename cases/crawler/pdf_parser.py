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
            # WHY return None instead of []:
            #   Many IRCC government PDFs (IMM5710, IMM5257, etc.) use XFA
            #   (XML Forms Architecture) — a completely different form spec that
            #   pypdf cannot read.  When pypdf finds an XFA-only PDF it returns
            #   None/empty from get_fields().  Returning None signals the caller
            #   to try PyMuPDF (fitz), which has better XFA support, rather than
            #   silently giving up and showing "No fields found".
            #
            # We detect XFA by looking for the /XFA key inside the PDF's
            # /AcroForm dictionary.  If /XFA is present, the form IS a form
            # (just one pypdf can't read), so we return None to trigger the
            # PyMuPDF path.  If there is genuinely no AcroForm at all, we
            # return [] because it is a static (non-fillable) PDF — no point
            # trying PyMuPDF.
            #
            # EXPAND: log a debug warning here so the admin can see in the
            #         Django console which PDFs triggered the XFA fallback.
            try:
                root     = reader.trailer.get('/Root', {})
                acroform = root.get('/AcroForm', {}) if hasattr(root, 'get') else {}
                if hasattr(acroform, 'get') and '/XFA' in acroform:
                    # ── XFA form detected ───────────────────────────────────────
                    # IRCC IMM forms (IMM5710, IMM5257, etc.) use XFA (XML Forms
                    # Architecture) — a completely different spec from AcroForm.
                    # Browser PDF viewers cannot render XFA at all (they show
                    # "can't open content of PDF") — only Adobe Reader can.
                    #
                    # WHY NOT TRY PYMUPDF: PyMuPDF's page.widgets() also returns
                    # nothing for XFA fields because it targets AcroForm widgets.
                    # The real data is in the /XFA array as raw XML streams.
                    #
                    # SOLUTION: extract the "template" packet from the /XFA array,
                    # parse the XML ourselves using Python's built-in xml.etree,
                    # and pull out field names + caption labels from <field> elements.
                    xfa_fields = _extract_xfa_fields_from_pypdf(reader)
                    if xfa_fields is not None:
                        return xfa_fields
                    return None  # XFA extraction also failed — try PyMuPDF stub
            except Exception:
                pass    # if anything goes wrong during detection, fall through to []
            return []   # genuinely static PDF (no AcroForm at all)

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


# ── XFA EXTRACTION (via pypdf + xml.etree) ───────────────────
#
# WHY needed: IRCC IMM PDFs use XFA, which browsers and pypdf/pymupdf widget APIs
# cannot parse. XFA stores field definitions as XML inside the PDF's /XFA stream.
# We extract the template packet and parse <field> elements ourselves.
#
# EXPAND: handle multi-page XFA (some IMM forms have 50+ pages of fields).
# EXPAND: add 'page_number' by tracking which <subform> group a field is in.

def _extract_xfa_fields_from_pypdf(reader) -> list[dict] | None:
    """
    Read the /XFA template XML from a pypdf PdfReader that has an XFA form.

    Returns:
        List of field dicts (same schema as AcroForm extraction) on success.
        None if the XFA XML cannot be found or parsed.

    HOW XFA IS STORED IN A PDF:
      The /AcroForm dict has a /XFA key whose value is an array of alternating
      packet names and indirect object references:
        [/template 5 0 R /datasets 6 0 R /config 7 0 R ...]
      Each indirect reference points to a PDF stream containing XML text.
      We look for the "template" packet because that's where field definitions live.

    EXPAND: also read the "datasets" packet to get current field values if needed.
    """
    try:
        root = reader.trailer['/Root']
        acroform = root.get('/AcroForm')
        if not acroform:
            return None
        # Resolve indirect reference if needed (pypdf lazy-loads objects)
        if hasattr(acroform, 'get_object'):
            acroform = acroform.get_object()

        xfa_obj = acroform.get('/XFA')
        if not xfa_obj:
            return None

        # /XFA can be a direct stream (single-packet) or an array (multi-packet).
        # Multi-packet is the common case for IMM forms.
        template_xml = None

        # Resolve array items — pypdf returns them as ArrayObject (iterable)
        try:
            items = list(xfa_obj)
        except TypeError:
            # Single stream — try reading it directly
            try:
                if hasattr(xfa_obj, 'get_object'):
                    xfa_obj = xfa_obj.get_object()
                if hasattr(xfa_obj, 'get_data'):
                    template_xml = xfa_obj.get_data().decode('utf-8', errors='replace')
            except Exception:
                pass
        else:
            # Walk pairs: [name_str, stream_ref, name_str, stream_ref, ...]
            for i in range(0, len(items) - 1, 2):
                try:
                    packet_name = str(items[i]).strip().lower().strip('/')
                    if 'template' not in packet_name:
                        continue
                    stream_ref = items[i + 1]
                    # Resolve the indirect reference to get the actual stream
                    if hasattr(stream_ref, 'get_object'):
                        stream_ref = stream_ref.get_object()
                    if hasattr(stream_ref, 'get_data'):
                        raw = stream_ref.get_data()
                        template_xml = raw.decode('utf-8', errors='replace')
                        break
                except Exception:
                    continue

        if not template_xml:
            return None

        return _parse_xfa_template_xml(template_xml)

    except Exception:
        return None


def _parse_xfa_template_xml(xml_text: str) -> list[dict]:
    """
    Parse an XFA template XML string and return field definitions.

    XFA template structure (simplified IRCC IMM example):
      <template xmlns="http://www.xfa.org/schema/xfa-template/3.0/">
        <subform name="form1">
          <subform name="Page1">
            <field name="FamilyName" w="..." h="...">
              <caption>
                <value><text>Family Name / Nom de famille</text></value>
              </caption>
              <ui><textEdit/></ui>
              <validate nullTest="error"/>
            </field>
            <field name="Married" ...>
              <caption><value><text>Married</text></value></caption>
              <ui><checkButton shape="check"/></ui>
            </field>
          </subform>
        </subform>
      </template>

    Returns:
        List of field dicts — same schema as AcroForm extraction.

    EXPAND: parse <items> children of <field> to extract dropdown choices.
    EXPAND: track which <subform> (page section) a field is in for form_section.
    """
    import xml.etree.ElementTree as ET
    import re

    fields = []
    seen_names = set()

    try:
        # ── Strip XML namespaces for simpler xpath/iteration ──────────────
        # XFA uses namespace-qualified elements like xfa:template. Python's
        # ElementTree requires explicit namespace handling which is verbose.
        # Easiest approach: strip all xmlns declarations and namespace prefixes
        # from the raw text so we can use plain tag names in .iter() and .find().
        #
        # WHY regex substitution (not ET namespace handling):
        #   XFA mixes many namespaces (xfa, xdp, soap, etc.).
        #   Stripping them is simpler and safe here because we only read the tree.
        clean = re.sub(r'\s+xmlns(?::\w+)?="[^"]*"', '', xml_text)  # remove xmlns= declarations
        clean = re.sub(r'<([/]?\w+):',               r'<\1_',       clean)  # prefix:tag → prefix_tag
        # Further simplify: strip any remaining namespace prefixes from tags
        clean = re.sub(r'<([/]?)[\w]+_(\w)',          r'<\1\2',      clean)  # <xfa_field → <field

        root_el = ET.fromstring(clean)
    except ET.ParseError:
        return []

    # ── Walk every <field> element anywhere in the tree ───────────────────
    # WHY .iter('field'): XFA nests fields inside subforms (page sections).
    # iter() recursively visits all descendants regardless of depth.
    for field_el in root_el.iter('field'):
        field_name = field_el.get('name', '').strip()
        if not field_name or field_name in seen_names:
            continue
        seen_names.add(field_name)

        # ── Extract caption (human-readable label) ────────────────────────
        # The caption hierarchy: <caption> → <value> → <text>text content</text>
        # Some fields have the label directly in a /TU (tooltip) attribute instead.
        label = ''
        caption_el = field_el.find('.//caption')
        if caption_el is not None:
            text_el = caption_el.find('.//text')
            if text_el is not None and text_el.text:
                label = text_el.text.strip()
        if not label:
            # Fall back to cleaning the field name (e.g. 'Section2_FamilyName' → 'Family Name')
            label = _clean_field_name(field_name)

        # ── Determine field type from the UI child element ────────────────
        # The <ui> element contains exactly one child whose tag name tells us
        # what kind of widget it is: textEdit, checkButton, choiceList, etc.
        field_type = 'text'
        ui_el = field_el.find('ui')
        if ui_el is not None:
            # Get the first child tag (there should be exactly one)
            ui_children = list(ui_el)
            if ui_children:
                ui_tag = ui_children[0].tag.lower()
                field_type = _map_xfa_ui_type(ui_tag)

        # ── Required flag ─────────────────────────────────────────────────
        # XFA uses <validate nullTest="error"> to mean "required".
        # nullTest="disabled" or absent means optional.
        is_required = False
        validate_el = field_el.find('validate')
        if validate_el is not None:
            is_required = (validate_el.get('nullTest', '') == 'error')

        # ── Dropdown options ──────────────────────────────────────────────
        # XFA stores options as <items> → <text> children.
        options = []
        for items_el in field_el.findall('.//items'):
            for val_el in items_el.findall('text'):
                if val_el.text:
                    options.append(val_el.text.strip())

        fields.append({
            'field_id':    field_name,
            'label':       label,
            'field_type':  field_type,
            'is_required': is_required,
            'options':     options,
        })

    return fields


def _map_xfa_ui_type(ui_tag: str) -> str:
    """
    Map an XFA <ui> child tag name to our internal field type string.

    XFA UI element tags (from XFA spec 3.3, section 12):
      textEdit     → single or multi-line text input
      checkButton  → checkbox (or sometimes radio button)
      choiceList   → dropdown / list box
      dateTimeEdit → date/time picker (treat as text — we store dates as text)
      numericEdit  → numeric input
      signature    → digital signature field
      imageEdit    → image/photo upload
    """
    tag = ui_tag.lower()
    if 'textedit'    in tag: return 'text'
    if 'checkbutton' in tag: return 'checkbox'
    if 'radiobutton' in tag: return 'radio'
    if 'choicelist'  in tag: return 'dropdown'
    if 'combobox'    in tag: return 'dropdown'
    if 'datetime'    in tag: return 'text'   # date stored as text field
    if 'numeric'     in tag: return 'text'   # number stored as text field
    if 'signature'   in tag: return 'signature'
    return 'text'


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
