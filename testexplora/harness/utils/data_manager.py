import json

def load_data(data_path, lite=False, subset=False):
    with open(data_path, "r") as f:
        data = json.load(f)
    if lite:
        lite_path = data_path.replace("tdd_bench_with_docstring.json", "data_flitered4_test.json")
        with open(lite_path, "r") as f:
            lite_data = json.load(f)
    else:
        lite_data = None

    if subset:
        with open("/home/superbench/jiaxiang/my_tddbench/my_tdd_bench/pr_results/sweagent-gpt5mini_merged_passing_prs.json", "r") as f:
            subset_data = json.load(f)
    else:
        subset_data = None
    allpr_len = 0
    repo_level_data = {}
    for item in data:
        repo_name = item["repo_name"]
        if lite_data is not None:
            if repo_name not in lite_data:
                continue
            if item["pr_id"] not in lite_data[repo_name]:
                continue
        if subset_data is not None:
            if repo_name not in subset_data:
                continue
            if item["pr_id"] not in subset_data[repo_name]:
                continue
        if repo_name not in repo_level_data:
            repo_level_data[repo_name] = []
        repo_level_data[repo_name].append(item)
        allpr_len += 1
    return repo_level_data, allpr_len

def load_data4eva(data_path):
    with open(data_path, "r") as f:
        data = json.load(f)
    repo_level_data = {}
    for item in data:
        repo_name = item["repo_name"]
        if repo_name not in repo_level_data:
            repo_level_data[repo_name] = {}
        repo_level_data[repo_name][item["pr_id"]] = item
    return repo_level_data