
with open("./score_200/data_prompt_variation.csv", "r", encoding="utf-8") as f:
    lines = f.readlines()

a = lines[0]

for line in lines[1:]:
    b = line.strip('\n')

    a_list = a.split(",")
    b_list = b.split(",")
    model_name = b_list[1]

    a_list = a_list[3:]
    b_list = b_list[3:]

    print(f"========== {model_name} ==========")

    N = 24

    # return_format
    return_format_acc = {
        "python": 0.0,
        "json": 0.0,
        "concise_xml": 0.0,
        "verbose_xml": 0.0,
    }
    for i in range(0, N):
        if "return_format_Python" in a_list[i]:
            acc = float(b_list[i].strip('%'))
            return_format_acc["python"] += acc
        elif "return_format_json" in a_list[i]:
            acc = float(b_list[i].strip('%'))
            return_format_acc["json"] += acc
        elif "return_format_verbose_xml" in a_list[i]:
            acc = float(b_list[i].strip('%'))
            return_format_acc["verbose_xml"] += acc
        else:
            acc = float(b_list[i].strip('%'))
            return_format_acc["concise_xml"] += acc

    for key in return_format_acc:
        print(f"return_format = {key}, acc = {float(return_format_acc[key] / 6.0)}")


    # function_doc_format
    func_doc_acc = {
        "python": 0.0,
        "json": 0.0,
        "xml": 0.0,
    }
    for i in range(0, N):
        if "function_doc_format_python" in a_list[i]:
            acc = float(b_list[i].strip('%'))
            func_doc_acc["python"] += acc
        elif "function_doc_format_json" in a_list[i]:
            acc = float(b_list[i].strip('%'))
            func_doc_acc["json"] += acc
        else:
            acc = float(b_list[i].strip('%'))
            func_doc_acc["xml"] += acc

    for key in func_doc_acc:
        print(f"function doc format = {key}, acc = {float(func_doc_acc[key] / 8)}")

    # has tool call tag
    tool_tag_acc = {
        "True": 0.0,
        "False": 0.0,
    }
    for i in range(0, N):
        if "has_tool_call_tag_True" in a_list[i]:
            acc = float(b_list[i].strip('%'))
            tool_tag_acc["True"] += acc
        else:
            acc = float(b_list[i].strip('%'))
            tool_tag_acc["False"] += acc

    for key in tool_tag_acc:
        print(f"has tool call tag = {key}, acc = {float(tool_tag_acc[key] / 12)}")