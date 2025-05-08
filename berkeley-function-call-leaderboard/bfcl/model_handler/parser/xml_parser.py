import xml.etree.ElementTree as ET
import ast
import json

def parse_verbose_xml_function_call(input_str):
    def auto_cast(value):
        """Try to automatically cast value to boolean, int, float, list, or leave as string."""
        val = value.strip()
        if val.lower() in ("true", "false"):
            return val.lower() == "true"
        try:
            # Try JSON decoding for arrays, dicts, numbers
            return json.loads(val)
        except Exception:
            try:
                return ast.literal_eval(val)
            except Exception:
                pass
        # Fallback: leave as string
        return val

    try:
        root = ET.fromstring(input_str)
        results = []

        for func_elem in root.findall("function"):
            func_name = func_elem.attrib.get("name")
            if not func_name:
                continue

            params = {}
            for param_elem in func_elem.findall("param"):
                param_name = param_elem.attrib.get("name")
                param_text = param_elem.text.strip() if param_elem.text else ""

                if param_name:
                    params[param_name] = auto_cast(param_text)

            results.append({func_name: params})

        return results
    except Exception:
        return []

def parse_concise_xml_function_call(input_str):
    root = ET.fromstring(input_str)
    results = []

    for func in root.findall('function'):
        func_name = func.attrib['name']
        params = {
            param.attrib['name']: ast.literal_eval(param.text)
            for param in func.findall('param')
        }
        results.append({func_name: params})

    return results
