# Customize your ICLR 2025 Recommendation

This repo contains the crawl result for all the activate submission of ICLR 2025.
All of them are annotated some text embeddings from google Gemini API.
You can use those embeddings to build your own ICLR 2025 recommendation paper list, by the self defined like and dislike title or (title, abstract) list.

Rather than just scanning too many paper directly, or use the openreview keyword searching engine to filter. I think the language model embeddings will do a better balance to filter the paper you may interested.

## Usage

## Basic Usage

1. fork this repo
2. open the github page for the fork repo
3. **Do the customization**: adjust the parameters in `.github/workflows/main.yml`, about your preference of the paper list, the number of paper your want, etc.
4. go to the github action page and trigger the action
5. get the result markdown in the artifact and the rendering pages in the github page of the fork repo

The page rendering is powered by [mystmd](https://github.com/jupyter-book/mystmd), in a very academic style.

If the title you type in `likes` and `dislikes` not in the ICLR2025 paper like, the action would request the google gemini api. So you have to get your own google gemini api key at [ai.google.dev](https://ai.google.dev/). and set the action secret environment as `GOOGLE_API_KEY=<YOUR API KEY>`

## The detailed process
```bash
pip install -r requirements.txt  # install the dependency
python main.py  # do the crawl, powered by crawl4ai
python get_embeddings.py
python get_markdown.py

pip install mystmd
myst start
```
