from io import BytesIO
import math
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile


_MAIN_NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
_REL_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
_PKG_REL_NS = 'http://schemas.openxmlformats.org/package/2006/relationships'
_CONTENT_NS = 'http://schemas.openxmlformats.org/package/2006/content-types'
_XML_NS = 'http://www.w3.org/XML/1998/namespace'

ET.register_namespace('', _MAIN_NS)
ET.register_namespace('r', _REL_NS)


def _column_name(index):
    name = ''
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _cell_value(cell):
    if cell is None:
        return ''
    if isinstance(cell, bool):
        return cell
    if isinstance(cell, (int, float)):
        if isinstance(cell, float) and not math.isfinite(cell):
            raise ValueError('Excel cells cannot contain non-finite numbers.')
        return cell
    if isinstance(cell, str):
        if len(cell) > 32767:
            raise ValueError('Excel cell text cannot exceed 32,767 characters.')
        return cell
    raise ValueError('Excel cells must contain text, numbers, booleans, or null.')


def _worksheet_xml(rows):
    root = ET.Element(f'{{{_MAIN_NS}}}worksheet')
    sheet_data = ET.SubElement(root, f'{{{_MAIN_NS}}}sheetData')
    for row_index, row in enumerate(rows, start=1):
        row_element = ET.SubElement(sheet_data, f'{{{_MAIN_NS}}}row', {'r': str(row_index)})
        for column_index, raw_value in enumerate(row, start=1):
            value = _cell_value(raw_value)
            cell = ET.SubElement(row_element, f'{{{_MAIN_NS}}}c', {
                'r': f'{_column_name(column_index)}{row_index}'
            })
            if isinstance(value, bool):
                cell.set('t', 'b')
                ET.SubElement(cell, f'{{{_MAIN_NS}}}v').text = '1' if value else '0'
            elif isinstance(value, (int, float)):
                ET.SubElement(cell, f'{{{_MAIN_NS}}}v').text = str(value)
            else:
                cell.set('t', 'inlineStr')
                inline_string = ET.SubElement(cell, f'{{{_MAIN_NS}}}is')
                text = ET.SubElement(inline_string, f'{{{_MAIN_NS}}}t')
                if value[:1].isspace() or value[-1:].isspace():
                    text.set(f'{{{_XML_NS}}}space', 'preserve')
                text.text = value
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)


def create_xlsx_workbook(sheet_name, rows):
    if not isinstance(sheet_name, str) or not 1 <= len(sheet_name) <= 31:
        raise ValueError('Excel worksheet names must be between 1 and 31 characters.')
    if any(character in sheet_name for character in '[]:*?/\\'):
        raise ValueError('Excel worksheet name contains an invalid character.')
    if not isinstance(rows, list) or not rows or len(rows) > 10001:
        raise ValueError('Excel export must contain between 1 and 10,001 rows.')
    if any(not isinstance(row, list) or len(row) > 100 for row in rows):
        raise ValueError('Excel export rows must be arrays with no more than 100 columns.')
    column_count = len(rows[0])
    if column_count == 0 or any(len(row) != column_count for row in rows):
        raise ValueError('Excel export rows must all have the same non-zero column count.')
    if len(rows) * column_count > 500000:
        raise ValueError('Excel export is too large to generate.')
    checked_rows = []
    text_length = 0
    for row in rows:
        checked_row = []
        for cell in row:
            value = _cell_value(cell)
            if isinstance(value, str):
                text_length += len(value)
                if text_length > 10000000:
                    raise ValueError('Excel export contains too much text to generate.')
                if any(ord(character) < 32 and character not in '\t\n\r' for character in value):
                    raise ValueError('Excel cells cannot contain control characters.')
            checked_row.append(value)
        checked_rows.append(checked_row)

    content_types = ET.Element(f'{{{_CONTENT_NS}}}Types')
    ET.SubElement(content_types, f'{{{_CONTENT_NS}}}Default', {
        'Extension': 'rels',
        'ContentType': 'application/vnd.openxmlformats-package.relationships+xml',
    })
    ET.SubElement(content_types, f'{{{_CONTENT_NS}}}Default', {
        'Extension': 'xml',
        'ContentType': 'application/xml',
    })
    ET.SubElement(content_types, f'{{{_CONTENT_NS}}}Override', {
        'PartName': '/xl/workbook.xml',
        'ContentType': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml',
    })
    ET.SubElement(content_types, f'{{{_CONTENT_NS}}}Override', {
        'PartName': '/xl/worksheets/sheet1.xml',
        'ContentType': 'application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml',
    })

    package_relationships = ET.Element(f'{{{_PKG_REL_NS}}}Relationships')
    ET.SubElement(package_relationships, f'{{{_PKG_REL_NS}}}Relationship', {
        'Id': 'rId1',
        'Type': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument',
        'Target': 'xl/workbook.xml',
    })

    workbook = ET.Element(f'{{{_MAIN_NS}}}workbook')
    sheets = ET.SubElement(workbook, f'{{{_MAIN_NS}}}sheets')
    ET.SubElement(sheets, f'{{{_MAIN_NS}}}sheet', {
        'name': sheet_name,
        'sheetId': '1',
        f'{{{_REL_NS}}}id': 'rId1',
    })

    workbook_relationships = ET.Element(f'{{{_PKG_REL_NS}}}Relationships')
    ET.SubElement(workbook_relationships, f'{{{_PKG_REL_NS}}}Relationship', {
        'Id': 'rId1',
        'Type': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet',
        'Target': 'worksheets/sheet1.xml',
    })

    output = BytesIO()
    with ZipFile(output, 'w', ZIP_DEFLATED) as workbook_file:
        workbook_file.writestr(
            '[Content_Types].xml',
            ET.tostring(content_types, encoding='utf-8', xml_declaration=True),
        )
        workbook_file.writestr(
            '_rels/.rels',
            ET.tostring(package_relationships, encoding='utf-8', xml_declaration=True),
        )
        workbook_file.writestr(
            'xl/workbook.xml',
            ET.tostring(workbook, encoding='utf-8', xml_declaration=True),
        )
        workbook_file.writestr(
            'xl/_rels/workbook.xml.rels',
            ET.tostring(workbook_relationships, encoding='utf-8', xml_declaration=True),
        )
        workbook_file.writestr('xl/worksheets/sheet1.xml', _worksheet_xml(checked_rows))
    output.seek(0)
    return output
