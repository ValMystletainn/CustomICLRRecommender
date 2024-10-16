import argparse
import functools
import json
import logging
import os
import random
import time
import itertools
from concurrent.futures import ThreadPoolExecutor

import google.generativeai as genai

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)
genai.configure(transport="rest")

parser = argparse.ArgumentParser()
parser.add_argument('--crawl_result_dir', type=str, default='outputs')
parser.add_argument('--max_thread', type=int, default=8)
args = parser.parse_args()

crawl_results = os.listdir(args.crawl_result_dir)
crawl_results = [os.path.join(args.crawl_result_dir, file_name) for file_name in crawl_results if file_name.endswith(".json")]
crawl_results.sort(key=lambda x: int(x.split('result')[1].split('.json')[0]))

get_embedding_funcs = []  # type: list[Callable]
embedding_to_file_name = []
embedding_to_inner_file_indices = []
embedding_to_fields = []


def retry_with_timeout_decorator(
    max_retries: int = 3,
    base_delay: int = 10,
    factor: int = 2,
    jitter: bool = True,
):
    """
    A retry decorator with exponentially increasing timeout.

    :param max_retries: Maximum number of retries
    :param base_delay: Base delay time in seconds
    :param factor: Factor by which to increase the delay
    :param jitter: If True, add jitter to the delay
    :return: the decorator that wraps the function
    """

    def decorator(func):
        @functools.wraps(func)
        def retry_calling() -> dict:
            retries = 0
            while retries < max_retries:
                try:
                    # Compute the current delay
                    delay = base_delay * (factor**retries)
                    if jitter:
                        delay += random.uniform(0, 1)  # Add jitter

                    return func()
                except Exception as e:
                    retries += 1
                    if retries >= max_retries:
                        return {
                            "embeddings": [0.0] * 768,
                        }
                    logger.info(
                        f"Fail in the try {retries}/{max_retries} in {delay:.2f} seconds..."
                    )
                    time.sleep(delay)

        return retry_calling

    return decorator

def combine_title_abs(title: str, abs: str):
    return f"# {title}\n\nAbstract: {abs}"

for file_name in crawl_results:
    with open(file_name, "rt") as f:
        dict_list = json.load(f)
    ## title embeddings
    batch_size = len(dict_list)
    get_embedding_funcs += [
        functools.partial(
            genai.embed_content,
            model="models/embedding-001",
            content=item["title"],
            task_type="clustering",
        )
        for item in dict_list
    ]
    embedding_to_file_name += [file_name] * batch_size
    embedding_to_inner_file_indices += list(range(batch_size))
    embedding_to_fields += ["title_embeddings"] * batch_size

    ## title + abstract embeddings

    batch_size = len(dict_list)
    get_embedding_funcs += [
        functools.partial(
            genai.embed_content,
            model="models/embedding-001",
            content=combine_title_abs(item["title"], item.get("abstract", "")),
            task_type="clustering",
        )
        for item in dict_list
    ]
    embedding_to_file_name += [file_name] * batch_size
    embedding_to_inner_file_indices += list(range(batch_size))
    embedding_to_fields += ["title_abs_embeddings"] * batch_size


# get_embedding_funcs = get_embedding_funcs[:100]  # TODO: delete it

get_embedding_funcs = [
    retry_with_timeout_decorator(
        max_retries=3,
        base_delay=10,
        factor=2,
        jitter=True,
    )(func)
    for func in get_embedding_funcs
]

with ThreadPoolExecutor(max_workers=args.max_thread) as executor:
    embeddings = list(executor.map(lambda func: func(), get_embedding_funcs))

embeddings = [d["embedding"] for d in embeddings]

grouped_by_file_indices = list(range(len(embeddings)))
grouped_by_file_indices.sort(key=lambda x: embedding_to_file_name[x])

for file_name, indices in itertools.groupby(grouped_by_file_indices):
    indices = list(indices)
    with open(file_name, "rt") as f:
        output_dicts = json.load(f)

    for index, embedding in zip(indices, embeddings):
        inner_index = embedding_to_inner_file_indices[index]
        field = embedding_to_fields[index]
        output_dicts[inner_index][embedding_to_fields[index]] = embedding
    
    with open(file_name + 'l', "wt") as f:  # TODO turn it to json
        json.dump(output_dicts, f, indent=4)
