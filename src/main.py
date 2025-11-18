import asyncio

from apify import Actor
from playwright.async_api import async_playwright

PROFILE_URL = "https://x.com/binance"
TWEETS_TO_COLLECT = 5


async def main() -> None:
    async with Actor:
        Actor.log.info(f"Opening profile: {PROFILE_URL}")

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--disable-gpu"],
            )

            context = await browser.new_context()
            page = await context.new_page()

            await page.goto(PROFILE_URL, wait_until="networkidle")
            await page.wait_for_timeout(5000)

            # Scroll to load enough tweets
            for _ in range(4):
                await page.mouse.wheel(0, 2000)
                await page.wait_for_timeout(1500)

            tweets = []

            # Prefer only real tweets: article elements that contain a <time> (filter out side cards)
            articles = await page.locator("article").all()
            Actor.log.info(f"Found {len(articles)} article candidates")

            for article in articles:
                # Ensure this article has a time element (likely a tweet, not a random card)
                time_locator = article.locator("time").first
                if await time_locator.count() == 0:
                    continue

                # 1) Preferred selector: official tweet text container
                tweet_text_locator = article.locator("div[data-testid='tweetText']").first

                # 2) Fallback: any text node with lang attribute
                lang_text_locator = article.locator("div[lang]").first

                text = ""

                if await tweet_text_locator.count() > 0:
                    text = (await tweet_text_locator.inner_text()).strip()
                elif await lang_text_locator.count() > 0:
                    text = (await lang_text_locator.inner_text()).strip()

                # Timestamp
                time = await time_locator.get_attribute("datetime")

                # Tweet URL (status link)
                link_locator = article.locator("a[href*='/status/']").first
                href = await link_locator.get_attribute("href") if await link_locator.count() > 0 else None
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

            for t in tweets:
                await Actor.push_data(t)

            Actor.log.info(f"Pushed {len(tweets)} tweets to dataset")
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
