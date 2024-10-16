import argparse
import asyncio
import json
import os

from crawl4ai import AsyncWebCrawler
from crawl4ai.async_crawler_strategy import AsyncPlaywrightCrawlerStrategy
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy
from playwright.async_api import Browser, Page
import random

parser = argparse.ArgumentParser()
parser.add_argument('--start_page', type=int, default=1)
parser.add_argument('--end_page', type=int, default=464)
parser.add_argument('--output_dir', type=str, default='outputs')
args = parser.parse_args()

async def page_loading_func(page: Page):
    global args
    global extraction_strategy
    start_page = args.start_page
    end_page = args.end_page
    ## To start page

    print(f"[HOOK] to the page {start_page} ...")
    while True:
        fisrt_title = await page.evaluate("document.querySelectorAll('#active-submissions > div > div > ul > li > div > h4 > a')[0].textContent")
        page_btns = await page.evaluate("Array.from(document.querySelectorAll('#active-submissions > div > div > nav > ul > li > a[href=\"#\"]')).map((i) => i.text)")
        available_pages = [int(page) for page in page_btns if str.isdigit(page)]
        if available_pages[0] <= start_page and start_page <= available_pages[-1]:
            ## jump to target pages
            await page.evaluate(
                f"""
                var page_btns = document.querySelectorAll('#active-submissions > div > div > nav > ul > li > a[href="#"]');
                var target_btn = Array.from(page_btns).filter(function(page_btn) {{
                    return page_btn.textContent.trim() === '{start_page}';
                }})[0];
                target_btn.click();
                """
            )
        else:
            ## jump to the last page
            await page.evaluate(
                f"""
                var page_btns = document.querySelectorAll('#active-submissions > div > div > nav > ul > li > a[href="#"]');
                var target_btn = Array.from(page_btns).filter(function(page_btn) {{
                    return page_btn.textContent.trim() === '{available_pages[-1]}';
                }})[0];
                target_btn.click();
                """
            )
        while True:
            ## wait for page loading
            await asyncio.sleep(0.5 + random.random())
            next_first_title = await page.evaluate("document.querySelectorAll('#active-submissions > div > div > ul > li > div > h4 > a')[0].textContent")
            if next_first_title != fisrt_title or start_page == 1:
                fisrt_title = next_first_title
                break
        if (
            available_pages[0] <= start_page
            and start_page <= available_pages[-1]
        ):
            print(f"current at {start_page}, {fisrt_title=}")
            break
        else:
            print(f"current at {available_pages[-1]}, {fisrt_title=}")

    ### 

    for page_num in range(start_page, end_page + 1):
        ##
        print(f"[HOOK] in the main loop, to the page {page_num}")
        page_btns = await page.evaluate("Array.from(document.querySelectorAll('#active-submissions > div > div > nav > ul > li > a[href=\"#\"]')).map((i) => i.text)")
        available_pages = [int(page) for page in page_btns if str.isdigit(page)]
        await page.evaluate(
            f"""
            var page_btns = document.querySelectorAll('#active-submissions > div > div > nav > ul > li > a[href="#"]');
            var target_btn = Array.from(page_btns).filter(function(page_btn) {{
                return page_btn.textContent.trim() === '{page_num}';
            }})[0];
            target_btn.click();
            """
        )
        while True:
            ## wait for page loading
            await asyncio.sleep(.5 + random.random())
            next_first_title = await page.evaluate("document.querySelectorAll('#active-submissions > div > div > ul > li > div > h4 > a')[0].textContent")
            if next_first_title != fisrt_title or page_num == start_page:
                fisrt_title = next_first_title
                break
        
        print(f"[HOOK] unroll all details")
        await page.evaluate(
            """
            console.log(target_btn);
            var show_detail_btns = document.querySelectorAll('a[data-toggle="collapse"]');
            show_detail_btns.forEach(function(btn) {
                btn.click();
            });
            """
        )
        html = await page.content()
        dict_list = extraction_strategy.extract("", html)
        if os.path.exists(args.output_dir):
            os.makedirs(args.output_dir, exist_ok=True)
        with open(os.path.join(args.output_dir, f"result{page_num}.json"), "wt") as f:
            json.dump(dict_list, f, indent=4)

extraction_strategy = JsonCssExtractionStrategy(
    schema = {
        "name": "activate submisson extractor",
        "baseSelector": "#active-submissions > div > div > ul > li",
        "fields": [
            {
                "name": "title",
                "selector": "h4",
                "type": "text",
            },
            {
                "name": "link_suffix",
                "selector": "h4 > a:nth-child(1)",
                "type": "attribute",
                "attribute": "href",
            },
            {
                "name": "link",
                "type": "computed",
                "expression": "'https://openreview.net' + link_suffix"
            },
            {
                "name": "pdf_link",
                "type": "computed",
                "expression": "'https://openreview.net/pdf?' + link_suffix.lstrip('/forum?')"
            },
            {
                "name": "keywords",
                "selector": "div.note-content > div:nth-child(1) > span",
                "type": "text", 
            },
            {
                "name": "abstract",
                "selector": "div.note-content-value.markdown-rendered",
                "type": "text",
            },
            
        ]
    }
)

async def main():
    crawler_strategy = AsyncPlaywrightCrawlerStrategy(verbose=True)
    crawler_strategy.set_hook('before_retrieve_html', page_loading_func)

    
    async with AsyncWebCrawler(
        verbose=True,
        crawler_strategy=crawler_strategy,
    ) as crawler:
        await crawler.arun(
            url="https://openreview.net/group?id=ICLR.cc/2025/Conference#tab-active-submissions",
            # url="https://openreview.net",
            bypass_cache=True,
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            wait_for="div#active-submissions",
            extraction_strategy=extraction_strategy,
        )


if __name__ == "__main__":
    asyncio.run(main())
