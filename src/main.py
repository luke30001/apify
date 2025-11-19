# src/main.py

from __future__ import annotations

from apify import Actor
from playwright.async_api import async_playwright

BINANCE_URL = "https://x.com/Binance"

# Questo codice gira nel browser (document.*)
TWEET_SCRAPER_JS = """
() => {
  const articles = Array.from(document.getElementsByTagName('article'));
  const results = [];

  for (const article of articles) {
    const fullText = (article.innerText || '').trim();
    // Skippa articoli che iniziano con 'Pinned'
    if (fullText.startsWith('Pinned')) continue;

    const tweetNodes = article.querySelectorAll('[data-testid="tweetText"]');
    const textParts = [];

    tweetNodes.forEach(node => {
      const t = (node.innerText || '').trim();
      if (t) textParts.push(t);
    });

    const tweetText = textParts.join('\\n').trim();
    if (tweetText) {
      results.push(tweetText);
    }
  }

  return results;
}
"""


async def main() -> None:
    """Entry point dell'Actor Apify."""
    async with Actor:
        Actor.log.info("Apro la pagina X.com/Binance...")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            # Carica la pagina di Binance su X
            await page.goto(BINANCE_URL, wait_until="networkidle")

            # Esegui lo snippet JS nel contesto della pagina
            tweets = await page.evaluate(TWEET_SCRAPER_JS)

            Actor.log.info(f"Trovati {len(tweets)} tweet non pinned, li salvo nel dataset...")

            # Salva i risultati nel dataset dell'Actor (uno per item)
            for t in tweets:
                await Actor.push_data({"tweet_text": t})

            await browser.close()

        Actor.log.info("Fatto.")
