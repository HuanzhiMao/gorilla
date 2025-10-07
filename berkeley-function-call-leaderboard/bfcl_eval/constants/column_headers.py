COLUMNS_NON_LIVE = [
    "Rank",
    "Model",
    "Vision Overall Acc",
    "Vision Base",
    "Vision Crop 169",
    "Vision Crop 43",
    "Vision Resize 169",
    "Vision Resize 43",
    "Vision Black White",
    "Vision Edge Detection",
    "Vision Red Green",
]


COLUMNS_LIVE = [
    "Rank",
    "Model",
    "Live Overall Acc",
    "AST Summary",
    "Python Simple AST",
    "Python Multiple AST",
    "Python Parallel AST",
    "Python Parallel Multiple AST",
    "Irrelevance Detection",
    "Relevance Detection",
]


COLUMNS_MULTI_TURN = [
    "Rank",
    "Model",
    "Multi Turn Overall Acc",
    "Base",
    "Miss Func",
    "Miss Param",
    "Long Context",
]


COLUMNS_AGENTIC = [
    "Rank",
    "Model",
    "Agentic Overall Acc",
    "Web Search Summary",
    "Web Search Base",
    "Web Search No Snippet",
    "Memory Summary",
    "Memory KV",
    "Memory Vector",
    "Memory Recursive Summarization",
]

# Format Sensitivity columns are not scored but informative
COLUMNS_FORMAT_SENS_PREFIX = [
    "Rank",
    "Model",
    "Format Sensitivity Max Delta",
    "Format Sensitivity Standard Deviation",
]

COLUMNS_OVERALL = [
    "Rank",
    "Overall Acc",
    "Model",
    "Model Link",
    "Total Cost ($)",
    "Latency Mean (s)",
    "Latency Standard Deviation (s)",
    "Latency 95th Percentile (s)",
    "Non-Live AST Acc",
    "Non-Live Simple AST",
    "Non-Live Multiple AST",
    "Non-Live Parallel AST",
    "Non-Live Parallel Multiple AST",
    "Live Acc",
    "Live Simple AST",
    "Live Multiple AST",
    "Live Parallel AST",
    "Live Parallel Multiple AST",
    "Multi Turn Acc",
    "Multi Turn Base",
    "Multi Turn Miss Func",
    "Multi Turn Miss Param",
    "Multi Turn Long Context",
    "Web Search Acc",
    "Web Search Base",
    "Web Search No Snippet",
    "Memory Acc",
    "Memory KV",
    "Memory Vector",
    "Memory Recursive Summarization",
    "Relevance Detection",
    "Irrelevance Detection",
    "Format Sensitivity Max Delta",
    "Format Sensitivity Standard Deviation",
    "Organization",
    "License",
]
