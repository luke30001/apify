import asyncio
from datetime import datetime, timezone

from apify import Actor
from playwright.async_api import async_playwright

PROFILE_HANDLE = "binance"
PROFILE_URL = f"https://x.com/{PROFILE_HANDLE}"

# How many tweets we *want* in the final output
TWEETS_TO_RETURN = 5
# How many tweets we *collect* before sorting/filtering
TWEETS_TO_COLLECT = 50


def parse_iso_time(value: str | None) -> datetime:
    """Parse X's ISO timestamps safely, return minimal datetime if invalid."""
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        # X usually uses ISO 8601 with Z suffix
        if value.endswith("Z"):
            value = value.replace("Z", "+00:00")
        return datetime.fromisoformat(value)
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)


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

            # Scroll a bit to load enough tweets into the DOM
            for _ in range(6):
                await page.mouse.wheel(0, 2000)
                await page.wait_for_timeout(1500)

            tweets: list[dict] = []

            articles = await page.locator("article").all()
            Actor.log.info(f"Found {len(articles)} <article> elements")

            for article in articles:
                # Only keep things that look like real tweets (must have <time>)
                time_locator = article.locator("time").first
                if await time_locator.count() == 0:
                    continue

                # Preferred tweet text container
                tweet_text_locator = article.locator("div[data-testid='tweetText']").first
                # Fallback: any language-tagged text
                lang_text_locator = article.locator("div[lang]").first

                text = ""

                if await tweet_text_locator.count() > 0:
                    text = (await tweet_text_locator.inner_text()).strip()
                elif await lang_text_locator.count() > 0:
                    text = (await lang_text_locator.inner_text()).strip()

                # Timestamp
                time_str = await time_locator.get_attribute("datetime")

                # Tweet URL
                link_locator = article.locator("a[href*='/status/']").first
                href = await link_locator.get_attribute("href") if await link_locator.count() > 0 else None
                if href and href.startswith("/"):
                    url = f"https://x.com{href}"
                else:
                    url = href

                # Skip if we somehow didn't get a status URL (unlikely but safe)
                if not url:
                    continue

                tweets.append(
                    {
                        "text": text,
                        "time": time_str,
                        "url": url,
                        "parsed_time": parse_iso_time(time_str),
                    }
                )

                if len(tweets) >= TWEETS_TO_COLLECT:
                    break

            # Deduplicate by URL (in case of DOM duplicates / threads)
            unique_by_url = {}
            for t in tweets:
                unique_by_url[t["url"]] = t
            deduped_tweets = list(unique_by_url.values())

            # Sort by parsed_time DESC (latest first)
            deduped_tweets.sort(key=lambda t: t["parsed_time"], reverse=True)

            latest = deduped_tweets[:TWEETS_TO_RETURN]

            # Drop helper field before saving
            for t in latest:
                t.pop("parsed_time", None)
                await Actor.push_data(t)

            Actor.log.info(f"Pushed {len(latest)} latest tweets to dataset")

            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
