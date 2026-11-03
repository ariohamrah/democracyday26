# Market data and publication

November 1 historical prices were technically recoverable from Kalshi's public API. A provisional local reconstruction selected 23:00 America/New_York and closing hourly yes-bid/yes-ask midpoints. It was never represented as the organizer's exact scoring snapshot.

Before publication, [Kalshi's published Data Terms](https://kalshi-public-docs.s3.amazonaws.com/kalshi-data-terms-of-service.pdf) were checked. Those terms restrict redistribution of archived datasets and other uses without permission. No redistribution permission was established in this task. Raw market snapshots, recovered quotes, and price-derived selections are therefore **excluded from the published repository**. Private local reconstruction artifacts are ignored by Git and are not required by reproduction. The forecast model itself never uses market prices.

The public default is `data/odds/organizer_odds.csv`, containing a header and no fabricated prices. To complete competition scoring, import the organizer's November 1 file using the documented schema. An odds file must identify the original snapshot timezone, timestamp, price definition, source, and candidate-versus-party settlement semantics. Reconstructed files must remain labeled provisional.

Update: the user explicitly requested current odds as a fallback. The revised score-optimized draft publishes our selections and their audit, while raw current quotes remain under ignored `private_outputs/`. These selections use live prices as a proxy and must not be described as optimized against the official November 1 prices. The earlier exclusion above refers to the historical reconstruction and original release.
