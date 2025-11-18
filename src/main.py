import asyncio

from apify import Actor
from playwright.async_api import async_playwright

PROFILE_URL = "https://x.com/binance"
TWEETS_TO_COLLECT = 5


async def main() -> None:
    # Actor context (handles config, storage, logging, etc.)
    async with Actor:
        Actor.log.info(f"Opening profile: {PROFILE_URL}")

        async with async_playwright() as p:
            # Launch Chromium; Apify exposes headless flag via Actor.configuration
            browser = await p.chromium.launch(
                headless=Actor.configuration.headless,
                args=["--disable-gpu"],
            )
            context = await browser.new_context()
            page = await context.new_page()

            await page.goto(PROFILE_URL, wait_until="networkidle")
            # Give X/Twitter some time to render tweets
            await page.wait_for_timeout(5000)

            # Scroll a bit to load more tweets
            for _ in range(3):
                await page.mouse.wheel(0, 1500)
                await page.wait_for_timeout(1500)

            tweets = []

            # Each tweet is typically an <article> element
            articles = await page.locator("article").all()
            Actor.log.info(f"Found {len(articles)} article elements")

            for article in articles:
                # Tweet text (main text node usually has lang attribute)
                text_locator = article.locator("div[lang]").first
                if await text_locator.count() == 0:
                    continue

                text = (await text_locator.inner_text()).strip()
                if not text:
                    continue

                # Timestamp
                time_locator = article.locator("time").first
                if await time_locator.count() > 0:
                    time = await time_locator.get_attribute("datetime")
                else:
                    time = None

                # Tweet URL
                link_locator = article.locator("a[href*='/status/']").first
                if await link_locator.count() > 0:
                    href = await link_locator.get_attribute("href")
                else:
                    href = None

                if href and href.startswith("/"):
                    url = f"https://x.com{href}"
                else:
                    url = href

                tweet = {
                    "text": text,
                    "time": time,
                    "url": url,
                }
                tweets.append(tweet)

                if len(tweets) >= TWEETS_TO_COLLECT:
                    break

            # Save to default dataset
            for t in tweets:
                await Actor.push_data(t)

            Actor.log.info(f"Pushed {len(tweets)} tweets to dataset")

            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
