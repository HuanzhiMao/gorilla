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
    def auto_cast(value):
        """Auto-cast string to bool, int, float, list, etc."""
        val = value.strip()
        if val.lower() == "true":
            return True
        if val.lower() == "false":
            return False
        try:
            return json.loads(val)
        except Exception:
            try:
                return ast.literal_eval(val)
            except Exception:
                return val  # fallback to string

    try:
        root = ET.fromstring(input_str)
        results = []

        for func_elem in root:
            func_name = func_elem.tag
            params = {
                k: auto_cast(v)
                for k, v in func_elem.attrib.items()
            }
            results.append({func_name: params})

        return results
    except Exception:
        return []