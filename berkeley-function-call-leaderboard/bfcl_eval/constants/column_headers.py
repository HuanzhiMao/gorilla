#### Text Modality ####

COLUMNS_TEXT_NON_LIVE = [
    "Rank",
    "Model",
    "Non-Live Overall Acc",
    "AST Summary",
    "Simple AST",
    "Python Simple AST",
    "Java Simple AST",
    "JavaScript Simple AST",
    "Multiple AST",
    "Parallel AST",
    "Parallel Multiple AST",
    "Irrelevance Detection",
]

COLUMNS_TEXT_LIVE = [
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

COLUMNS_TEXT_MULTI_TURN = [
    "Rank",
    "Model",
    "Multi Turn Overall Acc",
    "Base",
    "Miss Func",
    "Miss Param",
    "Long Context",
]

COLUMNS_TEXT_AGENTIC = [
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

COLUMNS_TEXT_OVERALL = [
    "Rank",
    "Overall Acc",
    "Model",
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
]

#### Audio Modalities (true_audio and text_audio share the same column structure) ####

COLUMNS_AUDIO_NON_LIVE = COLUMNS_TEXT_NON_LIVE
COLUMNS_AUDIO_LIVE = COLUMNS_TEXT_LIVE
COLUMNS_AUDIO_MULTI_TURN = COLUMNS_TEXT_MULTI_TURN

COLUMNS_AUDIO_OVERALL = [
    "Rank",
    "Overall Acc",
    "Model",
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
    "Relevance Detection",
    "Irrelevance Detection",
]

#### Vision Modality ####

COLUMNS_VISION_OVERALL = [
    "Rank",
    "Model",
    "Vision Overall Acc",
    "geoguessr Type 1",
    "geoguessr Type 2",
    "geoguessr Type 3",
]

#### Master Cross-Modality Overall ####

COLUMNS_OVERALL = [
    "Rank",
    "Overall Acc",
    "Model",
    "Model Link",
    "Total Cost ($)",
    "Latency Mean (s)",
    "Latency Standard Deviation (s)",
    "Latency 95th Percentile (s)",
    "Text Acc",
    "True Audio Acc",
    "Text Audio Acc",
    "Vision Acc",
    "Organization",
    "License",
]
