import matplotlib.pyplot as plt
import numpy as np

# plt_var = "function_doc_format"
plt_vars = ["return_format", "function_doc_format", "has_tool_tag"]


with open("./score_200/data_prompt_variation.csv", "r", encoding="utf-8") as f:
    lines = f.readlines()

a = lines[0]

models = []
all_data = {
    "return_format_python": [],
    "return_format_json": [],
    "return_format_concise_xml": [],
    "return_format_verbose_xml": [],
    "function_doc_format_python": [],
    "function_doc_format_json": [],
    "function_doc_format_xml": [],
    "has_tool_tag_true": [],
    "has_tool_tag_false": [],
}


for line in lines[1:]:
    b = line.strip('\n')

    a_list = a.split(",")
    b_list = b.split(",")
    model_name = b_list[1]
    models.append(model_name)

    a_list = a_list[3:]
    b_list = b_list[3:]

    # print(f"========== {model_name} ==========")

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
    
    all_data["return_format_python"].append(float(return_format_acc["python"] / 6.0))
    all_data["return_format_json"].append(float(return_format_acc["json"] / 6.0))
    all_data["return_format_concise_xml"].append(float(return_format_acc["concise_xml"] / 6.0))
    all_data["return_format_verbose_xml"].append(float(return_format_acc["verbose_xml"] / 6.0))
    
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
    all_data["function_doc_format_python"].append(float(func_doc_acc["python"] / 8.0))
    all_data["function_doc_format_json"].append(float(func_doc_acc["json"] / 8.0))
    all_data["function_doc_format_xml"].append(float(func_doc_acc["xml"] / 8.0))

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
    all_data["has_tool_tag_false"].append(float(tool_tag_acc["False"] / 12.0))
    all_data["has_tool_tag_true"].append(float(tool_tag_acc["True"] / 12.0))
    
for plt_var in plt_vars:
    if plt_var == "return_format":
        x = np.arange(len(models))
        width = 0.18

        colors = ['#4E79A7', '#F28E2B', '#59A14F', '#E15759']

        plt.figure(figsize=(10, 6))
        plt.bar(x - 1.5*width, all_data["return_format_python"], width, label='python', color=colors[0])
        plt.bar(x - 0.5*width, all_data["return_format_json"], width, label='json', color=colors[1])
        plt.bar(x + 0.5*width, all_data["return_format_verbose_xml"], width, label='verbose xml', color=colors[2])
        plt.bar(x + 1.5*width, all_data["return_format_concise_xml"], width, label='concise xml', color=colors[3])

        plt.xticks(x, models, rotation=30, fontsize=6)
        plt.ylabel("Accuracy (%)")
        plt.ylim(0, 90)
        plt.title("Changing Function Call Return Format")
        # plt.legend(loc='upper right', bbox_to_anchor=(1.5, 1.0))

        plt.legend(
            loc='upper right',
            bbox_to_anchor=(1, 1),
            ncol=4,
            frameon=True,
            fontsize=8
        )
        plt.tight_layout(rect=[0, 0, 1, 0.88])
        # plt.show()

        plt.savefig("./figures/return_format_compare.png", dpi=300, bbox_inches='tight')
        plt.close()
    elif plt_var == "function_doc_format":
        x = np.arange(len(models))
        width = 0.25

        colors = ['#4E79A7', '#F28E2B', '#59A14F']

        plt.figure(figsize=(10, 6))
        plt.bar(x - width, all_data["function_doc_format_json"], width, label='json', color=colors[0])
        plt.bar(x,         all_data["function_doc_format_xml"], width, label='xml', color=colors[1])
        plt.bar(x + width, all_data["function_doc_format_python"], width, label='python', color=colors[2])

        plt.xticks(x, models, rotation=30, fontsize=6)
        plt.ylabel("Accuracy (%)")
        plt.ylim(0, 90)
        plt.title("Changing Given Function Doc Format")
        # plt.legend(loc='upper right', bbox_to_anchor=(1.5, 1.0))

        plt.legend(
            loc='upper right',
            bbox_to_anchor=(1, 1),
            ncol=4,
            frameon=True,
            fontsize=8
        )
        plt.tight_layout(rect=[0, 0, 1, 0.88])
        # plt.show()

        plt.savefig("./figures/function_doc_format_compare.png", dpi=300, bbox_inches='tight')
        plt.close()
    elif plt_var == "has_tool_tag":
        x = np.arange(len(models))
        width = 0.25

        colors = ['#4E79A7', '#F28E2B']

        plt.figure(figsize=(10, 6))
        plt.bar(x - width/2, all_data["has_tool_tag_false"], width, label='no tool tag', color=colors[0])
        plt.bar(x + width/2, all_data["has_tool_tag_true"], width, label='has tool tag', color=colors[1])

        plt.xticks(x, models, rotation=30, fontsize=6)
        plt.ylabel("Accuracy (%)")
        plt.ylim(0, 90)
        plt.title("Adding Tool Call Tag")
        # plt.legend(loc='upper right', bbox_to_anchor=(1.5, 1.0))

        plt.legend(
            loc='upper right',
            bbox_to_anchor=(1, 1),
            ncol=4,
            frameon=True,
            fontsize=8
        )
        plt.tight_layout(rect=[0, 0, 1, 0.88])
        # plt.show()

        plt.savefig("./figures/has_tool_tag_compare.png", dpi=300, bbox_inches='tight')
        plt.close()
    else:
        print(f"plotting variable {plt_var} not supported")
        continue