import os

# Keywords to search for in filenames
TARGET_KEYWORDS = [
    # "function_doc_format_python",
    "return_format_concise_xml",
    "return_format_verbose_xml",
]

def should_delete(filename):
    return any(keyword in filename for keyword in TARGET_KEYWORDS)

def delete_matching_files(root_dir="."):
    for dirpath, dirnames, filenames in os.walk(root_dir):
        for filename in filenames:
            if should_delete(filename):
                full_path = os.path.join(dirpath, filename)
                try:
                    os.remove(full_path)
                    print(f"Deleted: {full_path}")
                except Exception as e:
                    print(f"Failed to delete {full_path}: {e}")

if __name__ == "__main__":
    delete_matching_files()