import argparse
import json
import os

import matplotlib.pyplot as plt
import numpy as np


def get_extra_embedding(text: str) -> np.ndarray:
    import google.generativeai as genai
    genai.configure(transport="rest")
    embedding_dict = genai.embed_content(
        model="models/embedding-001",
        content=text,
        task_type="clustering",
    )
    embedding = embedding_dict["embedding"]
    return np.array(embedding)

def build_paper_section(paper_dict: dict) -> str:
    title = paper_dict["title"]
    abstract = paper_dict.get("abstract", "No absctract")
    openreview_link = paper_dict["link"]
    pdf_link = paper_dict["pdf_link"]
    result = ""
    result += f"## {title}"
    result += "\n\n"
    result += f"\[[openreview]({openreview_link})\] \[[pdf]({pdf_link})\]"
    result += "\n\n"
    result += f"**Abstract** {abstract}"
    
    return result

def dump_data_cdf(data: np.ndarray):
    data_sorted = np.sort(data)
    cdf = np.arange(1, len(data_sorted) + 1) / len(data_sorted)
    plt.plot(data_sorted, cdf, marker='.', linestyle='none')
    plt.xlabel('favor score')
    plt.ylabel('CDF')
    plt.title('CDF of scores for those paper')
    plt.savefig("score_cdf.png", bbox_inches='tight')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--crawl_result_dir", type=str, default="outputs")
    parser.add_argument("--score_threshold", type=float)
    parser.add_argument("--num_threshold", type=int)
    parser.add_argument("--likes", nargs='+')
    parser.add_argument("--dislikes", nargs='+')
    parser.add_argument("--like_dislike_config", type=str)
    parser.add_argument("--embedding_from", type=str, choices=["title", "title_abs"], default="title")

    args = parser.parse_args()
    assert not(args.score_threshold is not None and args.num_threshold is not None), "`score threshold` and `num threshld` cannot be both set"
    assert not((args.likes is not None or args.dislikes is not None) and args.like_dislike_config is not None), "command line options passing likes, dislikes is conflicting with passing config file"

    embeddings = np.load(os.path.join(args.crawl_result_dir, "embeddings.npy"))
    crawl_results = [
        os.path.join(args.crawl_result_dir, p)
        for p in os.listdir(args.crawl_result_dir) if p.endswith(".json")
    ]
    crawl_results.sort(key=lambda x: int(x.split('result')[1].split('.json')[0]))
    paper_list = []  # type: list[dict[str, Any]]
    for crawl_result in crawl_results:
        with open(crawl_result, "r") as f:
            paper_list.extend(json.load(f))
    embedding_index_key = f"{args.embedding_from}_embedding_index"
    title_to_embedding_index_lut = {
        paper_dict["title"]: paper_dict[embedding_index_key]
        for paper_dict in paper_list
    }
    
    ## get projection weight by like and dislike
    score_projection_weight = np.zeros(embeddings.shape[1])
    if args.like_dislike_config is not None:
        with open(args.like_dislike_config, "r") as f:
            like_dislike_config = json.load(f)
        likes = like_dislike_config["likes"]
        dislikes = like_dislike_config["dislikes"]
    elif args.likes is not None:
        likes = args.likes
        dislikes = args.dislikes
    
    if likes is not None and len(likes) > 0:
        like_embeddings = np.array([
            embeddings[title_to_embedding_index_lut[title], :] 
            if title in title_to_embedding_index_lut 
            else get_extra_embedding(title)
            for title in likes
        ])
        score_projection_weight += np.mean(like_embeddings, axis=0)
    if dislikes is not None and len(dislikes) > 0:
        dislike_embeddings = np.array([
            embeddings[title_to_embedding_index_lut[title], :] 
            if title in title_to_embedding_index_lut 
            else get_extra_embedding(title)
            for title in dislikes
        ])
        score_projection_weight -= np.mean(dislike_embeddings, axis=0)
    
    scores = [
        score_projection_weight @ embeddings[d[embedding_index_key], :]
        for d in paper_list
    ]
    scores = np.array(scores)
    favor_indices = np.argsort(scores)[::-1]
    if args.score_threshold is not None:
        favor_indices = favor_indices[scores[favor_indices] > args.score_threshold]
    if args.num_threshold is not None:
        favor_indices = favor_indices[:args.num_threshold]
    
    favor_papers = [paper_list[i] for i in favor_indices]
    favor_scores = scores[favor_indices]

    ## output the markdown
    header = "# Your ICLR Recommendation list"
    header += "\n\n"
    header += f"There are {len(favor_papers)} papers for you in ICLR 2025"
    header += "\n\n"
    dump_data_cdf(favor_scores)
    header += "![score_cdf](score_cdf.png)"
    
    paper_section = "\n\n".join([build_paper_section(d) for d in favor_papers])

    markdown_str = header + "\n\n" + paper_section
    with open("output.md", "wt") as f:
        f.write(markdown_str)
    

if __name__ == "__main__":
    main()
